"""
test_simulator.py - Unit Test Simulator Smart Energy (Tim 1 - AIR24)
Memverifikasi kepatuhan penuh terhadap kontrak wanlubis/iotkampus-tim3-air24:
- Daftar 4 perangkat wajib (kwh-01..04, gedung bsd-a, ruang r3012/r3013/r3017/lab-iot)
- Format topik kampus/energy/bsd-a/{ruang}/{device_id}/{channel}
- Amplop kampus.telemetry.v1 & kampus.status.v1
- Akumulasi energy_kwh kumulatif non-menurun
- Mode NORMAL, BOROS, LONJAKAN, dan validasi status lowercase
"""

from datetime import datetime, timedelta, timezone
import unittest

from devices_config import (
    DEVICES,
    DEVICES_BY_ID,
    HIGH_LOAD_THRESHOLD_W,
    WASTE_THRESHOLD_W,
)
import simulator

WIB = timezone(timedelta(hours=7))


class TestEnergySimulatorContract(unittest.TestCase):
    def test_four_mandatory_devices_match_postgres_seed(self):
        self.assertEqual(len(DEVICES), 4)
        expected = {
            "kwh-01": ("bsd-a", "r3012"),
            "kwh-02": ("bsd-a", "r3013"),
            "kwh-03": ("bsd-a", "r3017"),
            "kwh-04": ("bsd-a", "lab-iot"),
        }
        for dev_id, (gedung, ruang) in expected.items():
            self.assertIn(dev_id, DEVICES_BY_ID)
            dev = DEVICES_BY_ID[dev_id]
            self.assertEqual(dev["domain"], "energy")
            self.assertEqual(dev["gedung"], gedung)
            self.assertEqual(dev["ruang"], ruang)

    def test_mqtt_topic_convention(self):
        dev = DEVICES_BY_ID["kwh-04"]
        self.assertEqual(simulator.telemetry_topic(dev), "kampus/energy/bsd-a/lab-iot/kwh-04/telemetry")
        self.assertEqual(simulator.status_topic(dev), "kampus/energy/bsd-a/lab-iot/kwh-04/status")
        self.assertEqual(simulator.heartbeat_topic(dev), "kampus/energy/bsd-a/lab-iot/kwh-04/heartbeat")
        self.assertEqual(simulator.cmd_topic(dev), "kampus/energy/bsd-a/lab-iot/kwh-04/cmd")

    def test_telemetry_v1_envelope_contract(self):
        dev = DEVICES_BY_ID["kwh-01"]
        state = simulator.EnergyMeterState(dev, mode="NORMAL")
        payload = state.step(dt_sec=5.0, now_dt=datetime(2026, 11, 23, 10, 0, tzinfo=WIB))

        self.assertEqual(payload["schema"], "kampus.telemetry.v1")
        self.assertIsInstance(payload["ts"], int)
        self.assertGreater(payload["ts"], 1_700_000_000_000)
        self.assertEqual(payload["device_id"], "kwh-01")
        self.assertEqual(payload["domain"], "energy")
        self.assertEqual(payload["gedung"], "bsd-a")
        self.assertEqual(payload["ruang"], "r3012")
        self.assertIn("metrics", payload)
        self.assertIsInstance(payload["metrics"]["power_w"], float)
        self.assertIsInstance(payload["metrics"]["energy_kwh"], float)
        self.assertNotIn("sim_after_hours", payload)

    def test_status_v1_envelope_and_lowercase_enforcement(self):
        dev = DEVICES_BY_ID["kwh-02"]
        online = simulator.make_status_payload(dev, "ONLINE")
        offline = simulator.make_status_payload(dev, "offline")
        self.assertEqual(online["schema"], "kampus.status.v1")
        self.assertEqual(online["status"], "online")
        self.assertEqual(offline["status"], "offline")
        self.assertIsInstance(online["ts"], int)
        with self.assertRaises(ValueError):
            simulator.make_status_payload(dev, "STOPPED")

    def test_energy_kwh_strictly_non_decreasing_and_accurate(self):
        dev = DEVICES_BY_ID["kwh-01"]
        state = simulator.EnergyMeterState(dev, mode="NORMAL", power_override_w=1000.0)
        start_kwh = state.energy_kwh

        # 1000 W selama 3600 detik = +1.0000 kWh
        p1 = state.step(dt_sec=3600.0)
        self.assertAlmostEqual(p1["metrics"]["energy_kwh"], start_kwh + 1.0, places=4)

        # Langkah kedua dengan 0 W tidak boleh menurunkan energy_kwh
        state.power_override_w = 0.0
        p2 = state.step(dt_sec=60.0)
        self.assertGreaterEqual(p2["metrics"]["energy_kwh"], p1["metrics"]["energy_kwh"])

    def test_normal_mode_respects_work_vs_after_hours_thresholds(self):
        dev = DEVICES_BY_ID["kwh-03"]
        state = simulator.EnergyMeterState(dev, mode="NORMAL")

        # Senin 10:00 WIB -> jam kerja
        work_dt = datetime(2026, 11, 23, 10, 0, tzinfo=WIB)
        self.assertTrue(simulator.is_work_hour_wib(work_dt))
        for _ in range(20):
            pw = state.sample_power_w(work_dt)
            self.assertLess(pw, HIGH_LOAD_THRESHOLD_W)

        # Senin 21:00 WIB -> luar jam kerja
        night_dt = datetime(2026, 11, 23, 21, 0, tzinfo=WIB)
        self.assertFalse(simulator.is_work_hour_wib(night_dt))
        for _ in range(20):
            pw = state.sample_power_w(night_dt)
            self.assertLessEqual(pw, WASTE_THRESHOLD_W)

        # Minggu 11:00 WIB -> akhir pekan (luar jam kerja)
        sunday_dt = datetime(2026, 11, 22, 11, 0, tzinfo=WIB)
        self.assertFalse(simulator.is_work_hour_wib(sunday_dt))

    def test_boros_and_lonjakan_fault_modes(self):
        dev = DEVICES_BY_ID["kwh-02"]

        boros_state = simulator.EnergyMeterState(dev, mode="BOROS")
        p_boros = boros_state.step(dt_sec=5.0)
        self.assertGreater(p_boros["metrics"]["power_w"], WASTE_THRESHOLD_W)
        self.assertTrue(p_boros.get("sim_after_hours"))

        lonjakan_state = simulator.EnergyMeterState(dev, mode="LONJAKAN")
        p_lonjakan = lonjakan_state.step(dt_sec=5.0)
        self.assertGreater(p_lonjakan["metrics"]["power_w"], HIGH_LOAD_THRESHOLD_W)

    def test_independent_mqtt_client_creation_with_lwt(self):
        dev = DEVICES_BY_ID["kwh-01"]
        state = simulator.EnergyMeterState(dev, mode="NORMAL")
        client = simulator.create_client(dev, state)
        self.assertIsNotNone(client)
        self.assertEqual(client._will_topic, b"kampus/energy/bsd-a/r3012/kwh-01/status")
        self.assertTrue(client._will_retain)
        self.assertEqual(client._will_qos, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
