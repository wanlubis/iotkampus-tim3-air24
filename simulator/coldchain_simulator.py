import json
import random
import time
import threading
import os
import math
import socket
import queue

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


# ==========================================
# KONFIGURASI MQTT
# ==========================================

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

if not MQTT_USERNAME or not MQTT_PASSWORD:
    raise ValueError(
        "MQTT_USERNAME dan MQTT_PASSWORD harus diatur di file .env"
    )

TELEMETRY_INTERVAL = 5
HEARTBEAT_INTERVAL = 15

MODES = ("NORMAL", "SPIKE", "DOOR", "STOP")

current_mode = "NORMAL"
mode_lock = threading.Lock()
chamber_lock = threading.Lock()
stop_event = threading.Event()
command_queue = queue.Queue()


# ==========================================
# DATA CHAMBER
# ==========================================

CHAMBERS = [
    {
        "device_id": "cc-01",
        "gedung": "bsd-a",
        "ruang": "gudang-a",
        "base_temp": 4.5,
        "setpoint_c": 4.5,
        "base_humidity": 65
    },
    {
        "device_id": "cc-02",
        "gedung": "bsd-a",
        "ruang": "gudang-a",
        "base_temp": 3.8,
        "setpoint_c": 3.8,
        "base_humidity": 62
    },
    {
        "device_id": "cc-03",
        "gedung": "bsd-a",
        "ruang": "gudang-b",
        "base_temp": 5.2,
        "setpoint_c": 5.2,
        "base_humidity": 70
    }
]


# ==========================================
# MODE SIMULATOR
# ==========================================

def get_mode():
    with mode_lock:
        return current_mode


def set_mode(new_mode):
    global current_mode

    new_mode = new_mode.upper()

    if new_mode not in MODES:
        print(f"[ERROR] Mode tidak dikenal: {new_mode}")
        return

    with mode_lock:
        current_mode = new_mode

    print(f"\n[MODE] Mode berubah menjadi {new_mode}\n")


# ==========================================
# MQTT TOPIC
# ==========================================

def topic_for(chamber, channel):
    return (
        f"kampus/coldchain/{chamber['gedung']}/"
        f"{chamber['ruang']}/{chamber['device_id']}/{channel}"
    )


# ==========================================
# PAYLOAD STANDAR
# ==========================================

def build_status_payload(chamber, status):
    return {
        "schema": "kampus.status.v1",
        "ts": int(time.time() * 1000),
        "device_id": chamber["device_id"],
        "domain": "coldchain",
        "gedung": chamber["gedung"],
        "ruang": chamber["ruang"],
        "status": status
    }


# ==========================================
# MQTT PUBLISH
# ==========================================

def publish_message(client, topic, payload, retain=False):
    if not client.is_connected():
        return False

    try:
        info = client.publish(
            topic,
            json.dumps(payload),
            qos=1,
            retain=retain
        )

        info.wait_for_publish(timeout=5)

        return info.is_published()

    except Exception as error:
        print(f"[ERROR] Publish gagal: {error}")
        return False


# ==========================================
# STATUS ONLINE / OFFLINE
# ==========================================

def publish_status(client, chamber, status):
    payload = build_status_payload(chamber, status)

    success = publish_message(
        client,
        topic_for(chamber, "status"),
        payload,
        retain=True
    )

    if success:
        print(
            f"[STATUS] {chamber['device_id']} | {status}"
        )


# ==========================================
# HEARTBEAT
# ==========================================

def publish_heartbeat(client, chamber):
    payload = build_status_payload(chamber, "online")

    if publish_message(
        client,
        topic_for(chamber, "heartbeat"),
        payload
    ):
        print(
            f"[HEARTBEAT] {chamber['device_id']} | online"
        )


# ==========================================
# TELEMETRY
# ==========================================

def publish_telemetry(client, chamber):
    mode = get_mode()

    with chamber_lock:
        setpoint = chamber["setpoint_c"]

    temperature = setpoint + random.uniform(-0.3, 0.3)

    humidity = (
        chamber["base_humidity"] +
        random.uniform(-2, 2)
    )

    door_open = random.random() < 0.05

    if mode == "SPIKE":
        temperature = random.uniform(8.5, 10.0)
        door_open = False

    elif mode == "DOOR":
        door_open = True

    payload = {
        "schema": "kampus.telemetry.v1",
        "ts": int(time.time() * 1000),
        "device_id": chamber["device_id"],
        "domain": "coldchain",
        "gedung": chamber["gedung"],
        "ruang": chamber["ruang"],
        "metrics": {
            "temp_c": round(temperature, 2),
            "humidity_pct": round(humidity, 2),
            "door_open": door_open,
            "battery_pct": 95,
            "rssi_dbm": -60,
            "setpoint_c": round(setpoint, 2)
        }
    }

    if publish_message(
        client,
        topic_for(chamber, "telemetry"),
        payload
    ):
        print(
            f"[TELEMETRY] {chamber['device_id']} | "
            f"Suhu: {temperature:.2f} C | "
            f"Setpoint: {setpoint:.2f} C | "
            f"Kelembapan: {humidity:.2f}% | "
            f"Pintu: {door_open} | "
            f"Mode: {mode}"
        )


# ==========================================
# CALLBACK MQTT CONNECT
# ==========================================

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties
):
    chamber = userdata["chamber"]
    device_id = chamber["device_id"]

    if reason_code == 0:

        client.subscribe(
            topic_for(chamber, "cmd"),
            qos=1
        )

        client.publish(
            topic_for(chamber, "status"),
            json.dumps(
                build_status_payload(chamber, "online")
            ),
            qos=1,
            retain=True
        )

        userdata["connected"].set()

        print(f"[MQTT] {device_id} terhubung.")
        print(f"[STATUS] {device_id} | online")
        print(
            f"[SUBSCRIBE] {topic_for(chamber, 'cmd')}"
        )

    else:
        print(
            f"[MQTT] {device_id} gagal: {reason_code}"
        )


# ==========================================
# CALLBACK MQTT DISCONNECT
# ==========================================

def on_disconnect(
    client,
    userdata,
    disconnect_flags,
    reason_code,
    properties
):
    userdata["connected"].clear()

    device_id = userdata["chamber"]["device_id"]

    print(
        f"[MQTT] {device_id} terputus: {reason_code}"
    )


# ==========================================
# CALLBACK MQTT COMMAND
# ==========================================

def on_message(client, userdata, message):
    chamber = userdata["chamber"]
    device_id = chamber["device_id"]

    if message.topic != topic_for(chamber, "cmd"):
        return

    try:
        payload = json.loads(
            message.payload.decode("utf-8")
        )

        if not isinstance(payload, dict):
            raise ValueError("Payload harus berupa object")

        command = payload.get("command")
        args = payload.get("args", {})

        if not isinstance(args, dict):
            raise ValueError("args harus berupa object")

        if command == "setpoint":

            raw_value = args.get("temp_c")

            if (
                isinstance(raw_value, bool)
                or not isinstance(raw_value, (int, float))
            ):
                raise ValueError(
                    "temp_c harus berupa angka"
                )

            new_setpoint = float(raw_value)

            if (
                not math.isfinite(new_setpoint)
                or not 0 <= new_setpoint <= 10
            ):
                raise ValueError(
                    "Setpoint harus antara 0-10 C"
                )

            with chamber_lock:
                old_setpoint = chamber["setpoint_c"]
                chamber["setpoint_c"] = new_setpoint

            print(
                f"\n[CMD] {device_id} | "
                f"Setpoint: {old_setpoint:.2f} C "
                f"-> {new_setpoint:.2f} C\n"
            )

        else:
            print(
                f"[CMD ERROR] {device_id} | "
                f"Command tidak dikenal: {command}"
            )

    except Exception as error:
        print(
            f"[CMD ERROR] {device_id} | {error}"
        )


# ==========================================
# MEMBUAT MQTT CLIENT
# ==========================================

def create_client(chamber):
    device_id = chamber["device_id"]
    connected = threading.Event()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"coldchain-{device_id}",
        userdata={
            "chamber": chamber,
            "connected": connected
        },
        reconnect_on_failure=False
    )

    client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    client.will_set(
        topic_for(chamber, "status"),
        json.dumps(
            build_status_payload(chamber, "offline")
        ),
        qos=1,
        retain=True
    )

    return client, connected


# ==========================================
# CONNECT CHAMBER
# ==========================================

def connect_chamber(chamber):
    device_id = chamber["device_id"]

    client, connected = create_client(chamber)

    try:
        print(f"[MQTT] Menghubungkan {device_id}...")

        client.connect(
            MQTT_HOST,
            MQTT_PORT,
            60
        )

        client.loop_start()

        if not connected.wait(15):
            raise RuntimeError(
                f"{device_id} gagal terhubung"
            )

        return {
            "client": client,
            "chamber": chamber,
            "connected": connected,
            "crashed": False
        }

    except Exception:
        client.disconnect()
        client.loop_stop()
        raise


# ==========================================
# CRASH CHAMBER
# ==========================================

def simulate_crash(clients, device_id):
    entry = clients.get(device_id)

    if entry is None:
        print(f"[ERROR] Device tidak ditemukan: {device_id}")
        return

    if entry["crashed"]:
        print(f"[CRASH] {device_id} sudah offline.")
        return

    client = entry["client"]

    print(
        f"\n[CRASH] Memutus koneksi {device_id}..."
    )

    # Menghentikan koneksi TCP tanpa MQTT DISCONNECT.
    # Broker akan menerbitkan Last Will and Testament.

    sock = client.socket()

    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            sock.close()
        except OSError:
            pass

    client.loop_stop()

    entry["connected"].clear()
    entry["crashed"] = True

    print(
        f"[CRASH] {device_id} offline. "
        "Chamber lainnya tetap berjalan.\n"
    )


# ==========================================
# RECONNECT CHAMBER
# ==========================================

def reconnect_chamber(clients, device_id):
    entry = clients.get(device_id)

    if entry is None:
        print(f"[ERROR] Device tidak ditemukan: {device_id}")
        return

    if (
        not entry["crashed"]
        and entry["connected"].is_set()
    ):
        print(f"[RECONNECT] {device_id} sudah online.")
        return

    try:
        entry["client"].loop_stop()

        print(
            f"\n[RECONNECT] Memulihkan {device_id}..."
        )

        clients[device_id] = connect_chamber(
            entry["chamber"]
        )

        print(
            f"[RECONNECT] {device_id} berhasil online.\n"
        )

    except Exception as error:
        print(
            f"[RECONNECT ERROR] {device_id} | {error}"
        )


# ==========================================
# STATUS SIMULATOR
# ==========================================

def show_status(clients):
    print("\n=== STATUS SIMULATOR ===")
    print(f"Mode: {get_mode()}")

    for device_id, entry in clients.items():

        with chamber_lock:
            setpoint = entry["chamber"]["setpoint_c"]

        status = (
            "online"
            if entry["connected"].is_set()
            else "offline"
        )

        print(
            f"{device_id} | "
            f"{status} | "
            f"Setpoint: {setpoint:.2f} C"
        )

    print("========================\n")


# ==========================================
# INPUT PERINTAH
# ==========================================

def print_commands():
    print("\n=== PERINTAH SIMULATOR ===")
    print("NORMAL")
    print("SPIKE")
    print("DOOR")
    print("STOP")
    print("CRASH cc-01")
    print("CRASH cc-02")
    print("CRASH cc-03")
    print("RECONNECT cc-01")
    print("RECONNECT cc-02")
    print("RECONNECT cc-03")
    print("STATUS")
    print("HELP")
    print("EXIT")
    print("==========================\n")


def command_listener():
    print_commands()

    while not stop_event.is_set():

        try:
            command = input("Mode> ").strip()

            if command:
                command_queue.put(command)

            if command.upper() == "EXIT":
                return

        except EOFError:
            stop_event.set()
            return


# ==========================================
# MEMPROSES PERINTAH
# ==========================================

def process_commands(clients):

    while not command_queue.empty():

        try:
            raw_command = command_queue.get_nowait()

        except queue.Empty:
            break

        parts = raw_command.split()
        action = parts[0].upper()

        if action in MODES:
            set_mode(action)

        elif action == "CRASH":

            device_id = (
                parts[1].lower()
                if len(parts) > 1
                else "cc-01"
            )

            simulate_crash(clients, device_id)

        elif action == "RECONNECT":

            device_id = (
                parts[1].lower()
                if len(parts) > 1
                else "cc-01"
            )

            reconnect_chamber(clients, device_id)

        elif action == "STATUS":
            show_status(clients)

        elif action == "HELP":
            print_commands()

        elif action == "EXIT":
            stop_event.set()
            return

        else:
            print(
                f"[ERROR] Perintah tidak dikenal: "
                f"{raw_command}"
            )


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():
    clients = {}

    try:

        for chamber in CHAMBERS:

            device_id = chamber["device_id"]

            clients[device_id] = connect_chamber(
                chamber
            )

        print(
            "\n=== SIMULATOR COLD-CHAIN AKTIF ==="
        )

        threading.Thread(
            target=command_listener,
            daemon=True
        ).start()

        last_telemetry = float("-inf")
        last_heartbeat = float("-inf")

        while not stop_event.is_set():

            process_commands(clients)

            if stop_event.is_set():
                break

            mode = get_mode()
            now = time.monotonic()

            # STOP menghentikan telemetry,
            # tetapi heartbeat dan status tetap online.

            if (
                mode != "STOP"
                and now - last_telemetry
                >= TELEMETRY_INTERVAL
            ):

                for entry in clients.values():

                    if (
                        not entry["crashed"]
                        and entry["connected"].is_set()
                    ):

                        publish_telemetry(
                            entry["client"],
                            entry["chamber"]
                        )

                last_telemetry = now

            # Heartbeat tetap berjalan selama
            # chamber masih terhubung.

            if (
                now - last_heartbeat
                >= HEARTBEAT_INTERVAL
            ):

                for entry in clients.values():

                    if (
                        not entry["crashed"]
                        and entry["connected"].is_set()
                    ):

                        publish_heartbeat(
                            entry["client"],
                            entry["chamber"]
                        )

                last_heartbeat = now

            stop_event.wait(0.2)

    except KeyboardInterrupt:

        print(
            "\n[SIMULATOR] Dihentikan pengguna."
        )

    except Exception as error:

        print(f"[ERROR] {error}")

    finally:

        stop_event.set()

        for entry in clients.values():

            client = entry["client"]
            chamber = entry["chamber"]

            try:

                if (
                    not entry["crashed"]
                    and client.is_connected()
                ):

                    publish_status(
                        client,
                        chamber,
                        "offline"
                    )

                    client.disconnect()

            finally:
                client.loop_stop()

        print(
            "[SIMULATOR] Simulator berhenti."
        )


if __name__ == "__main__":
    main()