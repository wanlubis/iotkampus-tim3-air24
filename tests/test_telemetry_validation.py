import os
import json
import time
import copy

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="coldchain-validation-test"
)

client.username_pw_set(
    os.getenv("MQTT_USERNAME") or os.getenv("MQTT_USER"),
    os.getenv("MQTT_PASSWORD")
)

client.connect("localhost", 1883, 60)
client.loop_start()

topic = "kampus/coldchain/bsd-a/gudang-a/cc-01/telemetry"

base = {
    "schema": "kampus.telemetry.v1",
    "ts": int(time.time() * 1000),
    "device_id": "cc-01",
    "domain": "coldchain",
    "gedung": "bsd-a",
    "ruang": "gudang-a",
    "metrics": {
        "temp_c": 4.5,
        "humidity_pct": 65.0,
        "door_open": False,
        "battery_pct": 95.0,
        "rssi_dbm": -55,
        "setpoint_c": 4.5
    }
}

cases = [
    ("INVALID_SCHEMA", ["schema"], "invalid.v1"),
    ("UNKNOWN_DEVICE", ["device_id"], "cc-999"),
    ("INVALID_LOCATION", ["ruang"], "gudang-z"),
    ("INVALID_TIMESTAMP", ["ts"], "invalid"),
    ("INVALID_METRIC", ["metrics", "temp_c"], "4.5"),
    ("INVALID_DOOR", ["metrics", "door_open"], "false"),
    ("INVALID_SETPOINT", ["metrics", "setpoint_c"], 99)
]

try:
    for name, path, value in cases:
        payload = copy.deepcopy(base)
        payload["ts"] = int(time.time() * 1000)

        target = payload

        for key in path[:-1]:
            target = target[key]

        target[path[-1]] = value

        result = client.publish(
            topic,
            json.dumps(payload),
            qos=1,
            retain=False
        )

        result.wait_for_publish(timeout=5)

        if not result.is_published():
            raise RuntimeError("Publish gagal: " + name)

        print(f"[SENT] {name}")
        time.sleep(2)

finally:
    client.disconnect()
    client.loop_stop()

print("[DONE] Pengiriman payload pengujian selesai")