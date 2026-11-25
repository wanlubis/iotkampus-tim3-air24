import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    API_KEY = os.getenv("API_KEY", "")

    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "kampus")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

    INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
    INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "prasmul")
    INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "iot")
    INFLUXDB_TOKEN = os.getenv("INFLUXDB_ADMIN_TOKEN", "")

    MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")


settings = Settings()