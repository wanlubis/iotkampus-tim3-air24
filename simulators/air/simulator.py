
import json
import os
import random
import time
import argparse
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME", "air24_user")
PASSWORD = os.getenv("MQTT_PASSWORD", "")

DEVICES = [
    {"id": "aq-01", "building": "gedung-a", "room": "ruang-101"},
    {"id": "aq-02", "building": "gedung-a", "room": "ruang-102"},
    {"id": "aq-03", "building": "gedung-b", "room": "ruang-201"},
]

MODES = [
    "NORMAL",
    "CO2_SPIKE",
    "PM_SPIKE",
    "NOISE_SPIKE",
    "STOP",
]


def generate_reading(mode):
    co2 = random.randint(400, 800)
    pm25 = round(random.uniform(5, 25), 2)
    noise = round(random.uniform(35, 60), 2)

    if mode == "CO2_SPIKE":
        co2 = random.randint(1600, 2000)

    elif mode == "PM_SPIKE":
        pm25 = round(random.uniform(80, 120), 2)

    elif mode == "NOISE_SPIKE":
        noise = round(random.uniform(75, 95), 2)

    return {
        "co2_ppm": co2,
        "pm25_ugm3": pm25,
        "noise_db": noise
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="NORMAL"
    )
    args = parser.parse_args()

    if args.mode == "STOP":
        print("Simulator stopped. No telemetry will be sent.")
        return

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="air24-simulator"
    )

    client.username_pw_set(USERNAME, PASSWORD)

    print(f"Connecting to MQTT broker: {BROKER}:{PORT}")

    client.connect(BROKER, PORT, 60)
    client.loop_start()

    try:
        while True:
            for device in DEVICES:
                metrics = generate_reading(args.mode)

                topic = (
                    f"kampus/air/{device['building']}/"
                    f"{device['room']}/{device['id']}/telemetry"
                )

                payload = {
                    "device_id": device["id"],
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "mode": args.mode,
                    "metrics": metrics
                }

                result = client.publish(
                    topic,
                    json.dumps(payload),
                    qos=1
                )

                result.wait_for_publish()

                print(f"[{device['id']}] {topic}")
                print(json.dumps(payload, indent=2))

            time.sleep(5)

    except KeyboardInterrupt:
        print("\nSimulator stopped.")

    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
