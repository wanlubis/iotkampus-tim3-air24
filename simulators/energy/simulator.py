#!/usr/bin/env python3
"""
simulator.py - Simulator 4 Smart Energy Meter (Tim 1 - AIR24)
Mengacu pada kontrak resmi monorepo wanlubis/iotkampus-tim3-air24:
- Topic: kampus/energy/{gedung}/{ruang}/{device_id}/{channel}
- Channel: telemetry (QoS 1), status (QoS 1, retain + LWT), heartbeat (QoS 0, 15s), cmd (QoS 1)
- Payload: kampus.telemetry.v1 (power_w, energy_kwh non-menurun) & kampus.status.v1 (online/offline)
- Mode: NORMAL, BOROS, LONJAKAN, STOP, CRASH
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import random
import signal
import time
import paho.mqtt.client as mqtt

from devices_config import (
    DEVICES,
    DEVICES_BY_ID,
    MODES,
    WORK_DAYS,
    WORK_END_HOUR,
    WORK_START_HOUR,
)

WIB = timezone(timedelta(hours=7))

BROKER = os.getenv("MQTT_HOST", os.getenv("MQTT_BROKER_HOST", "localhost"))
PORT = int(os.getenv("MQTT_PORT", os.getenv("MQTT_BROKER_PORT", "1883")))
USERNAME = os.getenv("MQTT_USERNAME", "air24_user")
PASSWORD = os.getenv("MQTT_PASSWORD", "")


def timestamp_ms() -> int:
    """Unix timestamp dalam milidetik UTC (wajib numerik per MQTT_CONTRACT.md)."""
    return time.time_ns() // 1_000_000


def is_work_hour_wib(dt: datetime | None = None) -> bool:
    """Cek apakah waktu WIB masuk jam kerja kampus (Senin-Jumat 07:00-18:00 WIB)."""
    wib_dt = (dt or datetime.now(WIB)).astimezone(WIB)
    return wib_dt.isoweekday() in WORK_DAYS and WORK_START_HOUR <= wib_dt.hour < WORK_END_HOUR


def telemetry_topic(device: dict) -> str:
    return f"kampus/energy/{device['gedung']}/{device['ruang']}/{device['id']}/telemetry"


def status_topic(device: dict) -> str:
    return f"kampus/energy/{device['gedung']}/{device['ruang']}/{device['id']}/status"


def heartbeat_topic(device: dict) -> str:
    return f"kampus/energy/{device['gedung']}/{device['ruang']}/{device['id']}/heartbeat"


def cmd_topic(device: dict) -> str:
    return f"kampus/energy/{device['gedung']}/{device['ruang']}/{device['id']}/cmd"


def make_status_payload(device: dict, status: str, ts_ms: int | None = None) -> dict:
    """Amplop standar kampus.status.v1 dengan nilai status wajib huruf kecil."""
    normalized = status.strip().lower()
    if normalized not in ("online", "offline"):
        raise ValueError(f"Status harus 'online' atau 'offline', diterima: {status}")
    return {
        "schema": "kampus.status.v1",
        "ts": ts_ms if ts_ms is not None else timestamp_ms(),
        "device_id": device["id"],
        "domain": "energy",
        "gedung": device["gedung"],
        "ruang": device["ruang"],
        "status": normalized,
    }


def make_heartbeat_payload(device: dict, ts_ms: int | None = None) -> dict:
    return {
        "ts": ts_ms if ts_ms is not None else timestamp_ms(),
        "device_id": device["id"],
        "domain": "energy",
        "status": "alive",
    }


def make_telemetry_payload(
    device: dict,
    power_w: float,
    energy_kwh: float,
    ts_ms: int | None = None,
    sim_after_hours: bool = False,
) -> dict:
    """Amplop standar kampus.telemetry.v1 untuk domain energy."""
    payload = {
        "schema": "kampus.telemetry.v1",
        "ts": ts_ms if ts_ms is not None else timestamp_ms(),
        "device_id": device["id"],
        "domain": "energy",
        "gedung": device["gedung"],
        "ruang": device["ruang"],
        "metrics": {
            "power_w": round(float(power_w), 2),
            "energy_kwh": round(float(energy_kwh), 4),
        },
    }
    if sim_after_hours:
        # Metadata di luar `metrics` agar InfluxDB tetap bersih (hanya angka),
        # sementara Node-RED dapat memicu WASTE_AFTER_HOURS saat demo siang hari.
        payload["sim_after_hours"] = True
    return payload


class EnergyMeterState:
    """Menyimpan state energi kumulatif non-menurun dan mode operasi per perangkat."""

    def __init__(self, device: dict, mode: str = "NORMAL", power_override_w: float | None = None):
        self.device = device
        self.mode = mode
        self.power_override_w = power_override_w
        self.energy_kwh = float(device["initial_kwh"])
        self.last_calc_monotonic = time.monotonic()

    def sample_power_w(self, dt: datetime | None = None) -> float:
        if self.power_override_w is not None:
            return max(0.0, float(self.power_override_w))

        if self.mode == "BOROS":
            # Ambang WASTE_AFTER_HOURS: > 200 W di luar jam kerja (2 menit)
            return round(random.uniform(450.0, 950.0), 2)
        if self.mode == "LONJAKAN":
            # Ambang HIGH_LOAD: > 3000 W (1 menit)
            return round(random.uniform(3300.0, 4400.0), 2)

        # Mode NORMAL
        if is_work_hour_wib(dt):
            low, high = self.device["work_power_w"]
        else:
            low, high = self.device["after_hours_power_w"]
        return round(random.uniform(low, high), 2)

    def step(self, dt_sec: float | None = None, now_dt: datetime | None = None) -> dict:
        now_mono = time.monotonic()
        elapsed = max(0.0, (now_mono - self.last_calc_monotonic) if dt_sec is None else float(dt_sec))
        self.last_calc_monotonic = now_mono

        power_w = self.sample_power_w(now_dt)
        delta_kwh = (power_w / 1000.0) * (elapsed / 3600.0)
        # Jamin energy_kwh kumulatif non-menurun
        self.energy_kwh = max(self.energy_kwh, self.energy_kwh + max(0.0, delta_kwh))

        return make_telemetry_payload(
            device=self.device,
            power_w=power_w,
            energy_kwh=self.energy_kwh,
            sim_after_hours=(self.mode == "BOROS"),
        )


def create_client(device: dict, meter_state: EnergyMeterState, client_suffix: str = "") -> mqtt.Client:
    """Membuat 1 MQTT client independen per meter dengan LWT offline (retain=True)."""
    cid = f"air24-{device['id']}" + (f"-{client_suffix}" if client_suffix else "")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid)

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)

    # Last Will and Testament (LWT): broker otomatis publish offline jika koneksi putus mendadak
    will_payload = make_status_payload(device, "offline")
    client.will_set(
        status_topic(device),
        json.dumps(will_payload),
        qos=1,
        retain=True,
    )

    def on_connect(cli, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            cli.subscribe(cmd_topic(device), qos=1)

    def on_message(cli, userdata, msg):
        try:
            body = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        command = str(body.get("command", "")).lower()
        args = body.get("args") or {}
        if command == "set_mode":
            new_mode = str(args.get("mode", "NORMAL")).upper()
            if new_mode in MODES:
                meter_state.mode = new_mode
                meter_state.power_override_w = (
                    float(args["power_w"]) if args.get("power_w") is not None else None
                )
                print(
                    f"[CMD] {device['id']} -> mode={meter_state.mode} "
                    f"(override={meter_state.power_override_w} W)"
                )
                if new_mode == "NORMAL":
                    birth = make_status_payload(device, "online")
                    cli.publish(status_topic(device), json.dumps(birth), qos=1, retain=True)
                elif new_mode == "CRASH":
                    print(f"[CMD/CRASH] {device['id']} mensimulasikan putus soket mendadak (LWT)...")
                    sock = cli.socket()
                    if sock is not None:
                        try:
                            sock.close()
                        except Exception:
                            pass

    client.on_connect = on_connect
    client.on_message = on_message
    return client


def parse_args():
    parser = argparse.ArgumentParser(description="Simulator 4 kWh Meter Smart Energy (Tim 1 - AIR24)")
    parser.add_argument("--mode", choices=MODES, default="NORMAL", help="Mode simulasi / injeksi gangguan")
    parser.add_argument(
        "--device",
        choices=[*DEVICES_BY_ID.keys(), "all"],
        default="all",
        help="Target perangkat (default: all)",
    )
    parser.add_argument("--interval", type=float, default=5.0, help="Interval telemetry dalam detik (default: 5)")
    parser.add_argument("--power-w", type=float, default=None, help="Override daya aktif dalam Watt (opsional)")
    parser.add_argument("--client-suffix", default="", help="Akhiran client_id opsional agar tidak bentrok")
    return parser.parse_args()


def main():
    args = parse_args()
    target_devices = DEVICES if args.device == "all" else [DEVICES_BY_ID[args.device]]

    print("=" * 64)
    print(" [AIR24] Tim 1 - Smart Energy 4-Meter Simulator")
    print(f" Broker   : {BROKER}:{PORT} (user={USERNAME or 'anonymous'})")
    print(f" Mode     : {args.mode}")
    print(f" Target   : {[d['id'] for d in target_devices]}")
    print(f" Interval : {args.interval}s | Heartbeat: 15s | QoS: 1")
    print("=" * 64)

    running = True

    def _stop_handler(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop_handler)
    signal.signal(signal.SIGTERM, _stop_handler)

    sessions: list[tuple[dict, EnergyMeterState, mqtt.Client]] = []
    try:
        for device in target_devices:
            state = EnergyMeterState(device, mode=args.mode, power_override_w=args.power_w)
            client = create_client(device, state, client_suffix=args.client_suffix)
            print(f"Connecting {device['id']} ({device['ruang']}) to {BROKER}:{PORT} ...")
            client.connect(BROKER, PORT, keepalive=60)
            client.loop_start()
            sessions.append((device, state, client))

            # Publish Birth Message: status = "online" (QoS 1, retain=True)
            birth = make_status_payload(device, "online")
            client.publish(status_topic(device), json.dumps(birth), qos=1, retain=True).wait_for_publish(timeout=5)
            print(f" -> [{device['id']}] Published BIRTH online (retain=True) -> {status_topic(device)}")

        cycle = 0
        last_heartbeat = 0.0

        while running:
            cycle += 1
            now_sec = time.time()

            # Cek apakah semua target dalam mode STOP
            active_telemetry = [s for s in sessions if s[1].mode != "STOP"]
            if not active_telemetry and cycle == 1:
                print("\n[STOP MODE] Status tetap ONLINE, transmisi telemetry & heartbeat dihentikan.")
                print("Menunggu timeout no-data 60 detik di Node-RED (tanpa memicu LWT)...")

            if active_telemetry:
                print(f"\n--- Siklus Telemetri #{cycle} ---")
                for device, state, client in active_telemetry:
                    payload = state.step()
                    topic = telemetry_topic(device)
                    client.publish(topic, json.dumps(payload), qos=1).wait_for_publish(timeout=5)
                    m = payload["metrics"]
                    tag = " [SIM_AFTER_HOURS]" if payload.get("sim_after_hours") else ""
                    print(
                        f"[{device['id']}|{device['ruang']}] "
                        f"mode={state.mode}{tag} | power_w={m['power_w']} W | energy_kwh={m['energy_kwh']} kWh"
                    )

                # Heartbeat setiap 15 detik (Bagian 4.1 & MQTT_CONTRACT.md)
                if now_sec - last_heartbeat >= 15.0:
                    last_heartbeat = now_sec
                    for device, state, client in active_telemetry:
                        hb_topic = heartbeat_topic(device)
                        hb_payload = make_heartbeat_payload(device)
                        client.publish(hb_topic, json.dumps(hb_payload), qos=0)
                        print(f"[{device['id']}] Heartbeat -> {hb_topic}")

            # Mode CRASH: putus koneksi secara paksa tanpa MQTT DISCONNECT agar broker menaikkan LWT offline
            if args.mode == "CRASH":
                print("\n[CRASH MODE] Mensimulasikan crash mendadak (abrupt socket drop) -> LWT offline!")
                time.sleep(1.0)
                os._exit(1)

            # Tidur bertahap agar responsif terhadap SIGINT/SIGTERM
            sleep_end = time.time() + args.interval
            while running and time.time() < sleep_end:
                time.sleep(0.25)

    finally:
        print("\n[SIMULATOR] Menghentikan simulator secara graceful -> publish status offline...")
        for device, state, client in sessions:
            try:
                off_payload = make_status_payload(device, "offline")
                client.publish(status_topic(device), json.dumps(off_payload), qos=1, retain=True).wait_for_publish(timeout=3)
                client.loop_stop()
                client.disconnect()
                print(f"[{device['id']}] Gracefully disconnected -> offline")
            except Exception as exc:
                print(f"[{device['id']}] Error saat disconnect: {exc}")


if __name__ == "__main__":
    main()
