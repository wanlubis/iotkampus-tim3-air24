from influxdb_client import InfluxDBClient

from app.config import settings


def get_influx_client():
    return InfluxDBClient(
        url=settings.INFLUXDB_URL,
        token=settings.INFLUXDB_TOKEN,
        org=settings.INFLUXDB_ORG,
    )


def query_influx(query: str):
    with get_influx_client() as client:
        result = client.query_api().query(
            query=query,
            org=settings.INFLUXDB_ORG,
        )

        records = []

        for table in result:
            for record in table.records:
                records.append(record.values)

        return records