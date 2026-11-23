# Contributors

Proyek: Mini IoT Platform Kampus
Tim: 3 AIR24

Dokumen ini menjelaskan pembagian kontribusi anggota berdasarkan
implementasi dan riwayat commit pada repository.

## 1. Alwan Aqthin

GitHub: wanlubis

Kontribusi:
- Initial project setup dan integrasi repository.
- Docker Compose orchestration.
- Implementasi database schema dan backend API.
- API authentication dan security.
- Integrasi Node-RED, Mosquitto, InfluxDB, dan Grafana.
- Final integration, konfigurasi keamanan, dan pengujian platform.

## 2. Herlina Wulandari Dewi

Kontribusi:
- Implementasi multi-node air quality simulator.
- Pengembangan event injection untuk simulasi kualitas udara.
- Pengembangan simulator dan integrasi Node-RED rule engine.
- Dokumentasi domain simulator energy dan coldchain.

## 3. Marina Evelin

Kontribusi:
- Implementasi backend API untuk domain air, coldchain, dan energy.
- Pengembangan dashboard monitoring dan visualisasi metrik.
- Penyusunan MQTT communication contracts.

---

## Tim 1: Smart Energy (AIR24)

### Aldy (Anggota 2 — API, Dashboard, Grafana & Unit Test)

GitHub: Aldy-create (`aldypasaribu59@gmail.com`)

Kontribusi:
- Implementasi REST API Smart Energy (`/api/v1/energy/rooms`, `/usage`, `/usage/export`, `/waste`, `/bill`, `/baseline`) pada `api/app/routers/energy.py`.
- Penambahan unit test endpoint & autentikasi Smart Energy pada `api/tests/test_energy_api.py`.
- Pengembangan tab Dashboard Smart Energy (`#content-energy`) dengan Full-Viewport 3D Digital Twin (Three.js), Floating Glassmorphism HUD, Expandable 2D Analytics Drawer (Chart.js), tabel kWh meter, dan ACK alert pada `dashboard/index.html`.
- Penambahan panel Grafana observabilitas Smart Energy (`power_w` dan `energy_kwh`) pada `grafana/provisioning/dashboards/air24_observability.json`.
- Dokumentasi peran, asumsi tarif/jam kerja, dan ringkasan API Smart Energy pada `README.md`.

## Catatan

Kontribusi anggota tercatat melalui riwayat commit Git.
Author menunjukkan pembuat perubahan, sedangkan committer
menunjukkan pihak yang mencatat commit ke repository.

Pembagian tanggung jawab ini merupakan ringkasan kontribusi
implementasi masing-masing anggota dalam proyek.
