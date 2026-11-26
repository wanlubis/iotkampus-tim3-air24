import json
import threading

import paho.mqtt.client as mqtt

from app.config import settings


def publish_command(topic: str, payload: dict) -> None:
    if not settings.MQTT_USERNAME or not settings.MQTT_PASSWORD:
        raise RuntimeError("MQTT credentials belum dikonfigurasi")

    connected = threading.Event()
    published = threading.Event()
    publish_result = {"success": False}
    connection_result = {"success": False}

    def on_connect(client, userdata, flags, reason_code, properties):
        connection_result["success"] = not reason_code.is_failure
        connected.set()

    def on_publish(client, userdata, mid, reason_code, properties):
        publish_result["success"] = not reason_code.is_failure
        published.set()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv5,
        reconnect_on_failure=False,
    )

    client.username_pw_set(
        settings.MQTT_USERNAME,
        settings.MQTT_PASSWORD,
    )

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.connect_timeout = 5

    try:
        client.connect(
            settings.MQTT_HOST,
            settings.MQTT_PORT,
            keepalive=30,
        )

        client.loop_start()

        if not connected.wait(timeout=5):
            raise RuntimeError("MQTT connection timeout")

        if not connection_result["success"]:
            raise RuntimeError("MQTT authentication or connection failed")

        result = client.publish(
            topic,
            payload=json.dumps(payload, allow_nan=False),
            qos=1,
            retain=False,
        )

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("MQTT publish failed")

        if not published.wait(timeout=5):
            raise RuntimeError("MQTT PUBACK timeout")

        if not publish_result["success"]:
            raise RuntimeError("MQTT publish rejected by broker")

    finally:
        client.disconnect()
        client.loop_stop()
