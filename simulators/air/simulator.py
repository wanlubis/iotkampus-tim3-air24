import json
import os
import random
import time
import argparse
import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME", "air24_user")
PASSWORD = os.getenv("MQTT_PASSWORD", "0")

DEVICES = [
    {"id": "aq-01", "gedung": "bsd-a", "ruang": "r3012"},
    {"id": "aq-02", "gedung": "bsd-a", "ruang": "r3017"},
    {"id": "aq-03", "gedung": "bsd-a", "ruang": "koridor-1"},
]

MODES = [
    "NORMAL",
    "CO2_SPIKE",
    "PM_SPIKE",
    "NOISE_SPIKE",
    "STOP",
    "CRASH",
]

def timestamp_ms():
    """Unix timestamp dalam milidetik UTC."""
    return time.time_ns() // 1_000_000

def generate_reading(mode):
    # Nilai normal standar
    co2 = random.randint(450, 850)
    pm25 = round(random.uniform(8.0, 25.0), 2)
    noise = round(random.uniform(40.0, 60.0), 2)

    # Injeksi Gangguan Sesuai Mode
    if mode == "CO2_SPIKE":
        # Ambang: >1000 warning, >1500 critical
        co2 = random.randint(1550, 2100)
    elif mode == "PM_SPIKE":
        # Ambang: >35 warning, >75 critical
        pm25 = round(random.uniform(80.0, 140.0), 2)
    elif mode == "NOISE_SPIKE":
        # Ambang: >70 warning
        noise = round(random.uniform(75.0, 95.0), 2)

    return {
        "co2_ppm": co2,
        "pm25_ugm3": pm25,
        "noise_db": noise
    }

def telemetry_topic(device):
    return f"kampus/air/{device['gedung']}/{device['ruang']}/{device['id']}/telemetry"

def status_topic(device):
    return f"kampus/air/{device['gedung']}/{device['ruang']}/{device['id']}/status"

def heartbeat_topic(device):
    return f"kampus/air/{device['gedung']}/{device['ruang']}/{device['id']}/heartbeat"

def make_heartbeat_payload(device):
    return {
        "ts": timestamp_ms(),
        "device_id": device["id"],
        "domain": "air",
        "status": "alive"
    }

def make_status_payload(device, status):
    return {
        "schema": "kampus.status.v1",
        "ts": timestamp_ms(),
        "device_id": device["id"],
        "domain": "air",
        "gedung": device["gedung"],
        "ruang": device["ruang"],
        "status": status
    }

def make_telemetry_payload(device, metrics):
    return {
        "schema": "kampus.telemetry.v1",
        "ts": timestamp_ms(),
        "device_id": device["id"],
        "domain": "air",
        "gedung": device["gedung"],
        "ruang": device["ruang"],
        "metrics": metrics
    }

def create_client(device):
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"air24-{device['id']}"
    )
    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)

    # LWT: broker akan otomatis menerbitkan payload offline jika client crash / koneksi putus tiba-tiba
    will_payload = make_status_payload(device, "offline")
    client.will_set(
        status_topic(device),
        json.dumps(will_payload),
        qos=1,
        retain=True
    )
    return client

def main():
    parser = argparse.ArgumentParser(description="Simulator Node Sensor Smart Environment (AIR24)")
    parser.add_argument("--mode", choices=MODES, default="NORMAL", help="Mode simulasi / injeksi gangguan")
    parser.add_argument("--device", choices=["aq-01", "aq-02", "aq-03", "all"], default="all", help="Target perangkat")
    parser.add_argument("--interval", type=int, default=5, help="Interval pengiriman telemetry (detik)")
    args = parser.parse_args()

    target_devices = DEVICES if args.device == "all" else [d for d in DEVICES if d["id"] == args.device]

    print("=" * 60)
    print(" [AIR24] Smart Environment (Air Quality) Sensor Simulator")
    print(f" Broker  : {BROKER}:{PORT}")
    print(f" Mode    : {args.mode}")
    print(f" Target  : {[d['id'] for d in target_devices]}")
    print(f" Interval: {args.interval}s")
    print("=" * 60)

    clients = []
    try:
        # Koneksikan setiap target client dan kirim birth message ONLINE
        for device in target_devices:
            client = create_client(device)
            print(f"Connecting {device['id']} to {BROKER}:{PORT} ...")
            client.connect(BROKER, PORT, 60)
            client.loop_start()
            clients.append((device, client))

            # Publish birth message (online) dengan retain = True
            birth_payload = make_status_payload(device, "online")
            client.publish(
                status_topic(device),
                json.dumps(birth_payload),
                qos=1,
                retain=True
            ).wait_for_publish()
            print(f" -> [{device['id']}] Published BIRTH ONLINE (retain=True)")

        # Mode STOP: Berhenti mengirim telemetry, namun koneksi TCP & status tetap ONLINE (uji No-Data)
        if args.mode == "STOP":
            print("\n[STOP MODE] Status tetap ONLINE, namun transmisi telemetri dihentikan.")
            print("Gunakan ini untuk menguji deteksi hilangnya data (no-data 60 detik) tanpa LWT.")
            while True:
                time.sleep(1)

        # Loop pengiriman Telemetry & Heartbeat
        cycle = 0
        last_heartbeat = 0
        while True:
            cycle += 1
            now_sec = time.time()
            print(f"\n--- Siklus Telemetri #{cycle} (Mode: {args.mode}) ---")
            for device, client in clients:
                metrics = generate_reading(args.mode)
                payload = make_telemetry_payload(device, metrics)
                topic = telemetry_topic(device)

                client.publish(topic, json.dumps(payload), qos=1).wait_for_publish()
                print(f"[{device['id']}] CO2: {metrics['co2_ppm']} ppm | PM2.5: {metrics['pm25_ugm3']} µg/m³ | Noise: {metrics['noise_db']} dB")

            # Kirim Heartbeat setiap 15 detik (Bagian 4.1 & 7.2)
            if now_sec - last_heartbeat >= 15:
                last_heartbeat = now_sec
                for device, client in clients:
                    hb_topic = heartbeat_topic(device)
                    hb_payload = make_heartbeat_payload(device)
                    client.publish(hb_topic, json.dumps(hb_payload), qos=0)
                    print(f"[{device['id']}] Heartbeat published -> {hb_topic}")

            # Mode CRASH: Putus koneksi secara mendadak agar broker menaikkan LWT Offline
            if args.mode == "CRASH":
                print("\n[CRASH MODE] Mensimulasikan crash mendadak (abrupt socket drop)...")
                time.sleep(1)
                os._exit(1)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nSimulator dihentikan oleh pengguna. Mengirim status OFFLINE secara graceful...")
    finally:
        for device, client in clients:
            try:
                offline_payload = make_status_payload(device, "offline")
                client.publish(status_topic(device), json.dumps(offline_payload), qos=1, retain=True).wait_for_publish(timeout=3)
                client.loop_stop()
                client.disconnect()
                print(f"[{device['id']}] Gracefully disconnected -> OFFLINE")
            except Exception as e:
                print(f"Error disconnecting {device['id']}: {e}")

if __name__ == "__main__":
    main()
