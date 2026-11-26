
import os
import json
import time
import copy

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


load_dotenv()

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="coldchain-status-validation-test",
)

client.username_pw_set(
    os.getenv("MQTT_USERNAME") or os.getenv("MQTT_USER"),
    os.getenv("MQTT_PASSWORD"),
)

client.connect("localhost", 1883, 60)
client.loop_start()


STATUS_TOPIC = (
    "kampus/coldchain/bsd-a/gudang-a/cc-01/status"
)

HEARTBEAT_TOPIC = (
    "kampus/coldchain/bsd-a/gudang-a/cc-01/heartbeat"
)


base = {
    "schema": "kampus.status.v1",
    "ts": int(time.time() * 1000),
    "device_id": "cc-01",
    "domain": "coldchain",
    "gedung": "bsd-a",
    "ruang": "gudang-a",
    "status": "online",
}


cases = [
    (
        "INVALID_SCHEMA",
        {"schema": "invalid.status.v1"},
        STATUS_TOPIC,
    ),
    (
        "UNKNOWN_DEVICE",
        {"device_id": "cc-999"},
        STATUS_TOPIC,
    ),
    (
        "INVALID_DOMAIN",
        {"domain": "energy"},
        STATUS_TOPIC,
    ),
    (
        "INVALID_LOCATION",
        {"ruang": "gudang-z"},
        STATUS_TOPIC,
    ),
    (
        "INVALID_TIMESTAMP",
        {"ts": "invalid"},
        STATUS_TOPIC,
    ),
    (
        "INVALID_STATUS",
        {"status": "unknown"},
        STATUS_TOPIC,
    ),
    (
        "INVALID_TOPIC",
        {},
        "kampus/coldchain/bsd-a/gudang-a/cc-02/status",
    ),
    (
        "OFFLINE_HEARTBEAT",
        {"status": "offline"},
        HEARTBEAT_TOPIC,
    ),
]


try:
    for name, changes, topic in cases:
        payload = copy.deepcopy(base)
        payload["ts"] = int(time.time() * 1000)
        payload.update(changes)

        result = client.publish(
            topic,
            json.dumps(payload),
            qos=1,
            retain=False,
        )

        result.wait_for_publish(timeout=5)

        if not result.is_published():
            raise RuntimeError(
                "Publish gagal: " + name
            )

        print(f"[SENT] {name}")

        time.sleep(2)

finally:
    client.disconnect()
    client.loop_stop()


print("[DONE] Pengiriman payload pengujian selesai")
