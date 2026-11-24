#!/usr/bin/env python3
"""
inject.py - Fault & Event Injector untuk Smart Energy (Tim 1 - AIR24)
Digunakan saat demo live (menit 8-12) untuk memicu skenario:
- boros    : power_w > 200 W (simulasi luar jam kerja -> WASTE_AFTER_HOURS warning setelah 2 menit)
- lonjakan : power_w > 3000 W (HIGH_LOAD critical setelah 1 menit)
- stop     : hentikan telemetry & heartbeat tanpa disconnect (uji deteksi OFFLINE 60 detik tanpa LWT)
- crash    : putus koneksi mendadak tanpa graceful disconnect (uji LWT offline)
- normal   : kembalikan perangkat ke operasi normal (memicu pemulihan / auto-resolve)
"""

import argparse
import json
import os
import subprocess
import sys
import paho.mqtt.client as mqtt

from devices_config import DEVICES, DEVICES_BY_ID

BROKER = os.getenv("MQTT_HOST", os.getenv("MQTT_BROKER_HOST", "localhost"))
PORT = int(os.getenv("MQTT_PORT", os.getenv("MQTT_BROKER_PORT", "1883")))
USERNAME = os.getenv("MQTT_USERNAME", "air24_user")
PASSWORD = os.getenv("MQTT_PASSWORD", "")

ACTION_TO_MODE = {
    "normal": "NORMAL",
    "boros": "BOROS",
    "lonjakan": "LONJAKAN",
    "stop": "STOP",
    "crash": "CRASH",
}


def cmd_topic(device: dict) -> str:
    return f"kampus/energy/{device['gedung']}/{device['ruang']}/{device['id']}/cmd"


def send_cmd_over_mqtt(target_devices: list[dict], mode: str, power_w: float | None = None) -> None:
    """Kirim perintah ganti mode ke simulator yang sedang berjalan melalui channel MQTT cmd."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"energy-injector-{os.getpid()}")
    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)

    client.connect(BROKER, PORT, keepalive=30)
    client.loop_start()
    try:
        for dev in target_devices:
            topic = cmd_topic(dev)
            payload = {
                "command": "set_mode",
                "args": {
                    "mode": mode,
                    **({"power_w": power_w} if power_w is not None else {}),
                },
            }
            info = client.publish(topic, json.dumps(payload), qos=1)
            info.wait_for_publish(timeout=5)
            print(f"[INJECT CMD] {dev['id']} ({dev['ruang']}) -> {topic} | mode={mode}")
    finally:
        client.loop_stop()
        client.disconnect()


def run_standalone_simulator(device_arg: str, mode: str, power_w: float | None = None, interval: float = 5.0) -> None:
    """Jalankan simulator.py langsung dalam mode gangguan (pola identik simulators/air/inject_event.py)."""
    sim_path = os.path.join(os.path.dirname(__file__), "simulator.py")
    cmd = [sys.executable, sim_path, "--mode", mode, "--device", device_arg, "--interval", str(interval)]
    if power_w is not None:
        cmd.extend(["--power-w", str(power_w)])
    print(f"[INJECT RUN] Menjalankan: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\n[INJECTOR] Dihentikan oleh pengguna.")


def main():
    parser = argparse.ArgumentParser(description="Fault & Event Injector Smart Energy (Tim 1 - AIR24)")
    parser.add_argument(
        "action",
        choices=list(ACTION_TO_MODE.keys()),
        help="Skenario gangguan: normal | boros | lonjakan | stop | crash",
    )
    parser.add_argument(
        "--device",
        "-d",
        default="kwh-01",
        choices=[*DEVICES_BY_ID.keys(), "all"],
        help="Target perangkat (default: kwh-01)",
    )
    parser.add_argument(
        "--via",
        choices=["run", "cmd"],
        default="run",
        help="'run' = jalankan simulator mode gangguan langsung (default); 'cmd' = kirim perintah MQTT cmd ke simulator aktif",
    )
    parser.add_argument(
        "--power-w",
        "-p",
        type=float,
        default=None,
        help="Override daya aktif dalam Watt (opsional)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Interval telemetry detik (khusus --via run, default: 5)",
    )
    args = parser.parse_args()

    mode = ACTION_TO_MODE[args.action]
    target_devices = DEVICES if args.device == "all" else [DEVICES_BY_ID[args.device]]

    print("=" * 60)
    print(f" [INJECTOR TIM 1] Action: {args.action.upper()} -> Mode: {mode}")
    print(f" Target: {[d['id'] for d in target_devices]} | Via: {args.via}")
    print("=" * 60)

    if args.via == "cmd":
        send_cmd_over_mqtt(target_devices, mode, power_w=args.power_w)
    else:
        run_standalone_simulator(args.device, mode, power_w=args.power_w, interval=args.interval)


if __name__ == "__main__":
    main()
