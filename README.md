# Smart Energy Monitoring (Tim 1 — AIR24)
**CSEB3073 IoT Cloud & Backend · Semester Ganjil 2026/2027 · Universitas Prasetiya Mulya**

Dokumentasi khusus domain **Smart Energy (Tim 1)** pada platform **Mini IoT Platform Kampus** — mencakup simulator 4 kWh meter, *rule engine* Node-RED, REST API FastAPI, panel observabilitas Grafana, serta antarmuka Dashboard BMS berbasis **Interactive 2D SVG Floor Plan** untuk **Lantai 3 Gedung BSD-A**.

---

## 1. Pembagian Peran Anggota Tim 1 (Smart Energy)

| Nama Anggota | Kontak GitHub | Peran Utama | Folder Tanggung Jawab |
|---|---|---|---|
| **Vincent Junio Ibrahim (`VozzyJun`)** | `vincentjunio1@gmail.com` | Owner Simulator 4 kWh Meter, Injektor Gangguan, & Rule Engine Energy Node-RED | `simulators/energy/`, `nodered/` (tab `Rules - Smart Energy`) |
| **Aldy Alfaisal Pasaribu (`Aldy-create`)** | `aldypasaribu59@gmail.com` | Owner REST API Smart Energy (`/api/v1/energy/*`), Tab Dashboard Smart Energy (BMS 2D SVG Floor Plan), Panel Grafana, & Unit Test | `api/app/routers/energy.py`, `api/tests/test_energy_api.py`, `dashboard/` (`#content-energy`, `dashboard/energy/`), `grafana/` |

---

## 2. Arsitektur & Layanan (Docker Compose)

Seluruh layanan berjalan lokal menggunakan Docker Compose (Windows WSL2):

| Layanan | Port Host | URL / Endpoint | Peran di Domain Smart Energy |
|---|---|---|---|
| **mosquitto** | 1883 | `mqtt://localhost:1883` | Broker MQTT dengan autentikasi user/password (`allow_anonymous false`) |
| **nodered** | 1880 | `http://localhost:1880` | Ingest telemetri, validasi skema, dan tab `Rules - Smart Energy` |
| **influxdb** | 8086 | `http://localhost:8086` | Penyimpanan time-series `power_w`, `energy_kwh`, `status`, `alerts` (`prasmul/iot`) |
| **postgres** | 5432 | `localhost:5432` | Registry master `devices` & riwayat `alert_events` + ACK (`kampus`) |
| **api** | 8000 | `http://localhost:8000` | FastAPI REST API `/api/v1/energy/*` & `/docs` (wajib header `X-API-Key`) |
| **dashboard** | 8080 | `http://localhost:8080` | Antarmuka BMS Smart Energy (denah SVG 2D, KPI, grafik Chart.js, ACK) |
| **grafana** | 3000 | `http://localhost:3000` | Observability panel `power_w` dan `energy_kwh` |
| **energy-simulator** | - | Profile `team-1` | Simulator 4 kWh meter (`kwh-01` s.d. `kwh-04`) |

---

## 3. Peta Topic MQTT & Daftar Perangkat Smart Energy

### Konvensi Topic
```text
kampus/energy/bsd-a/{ruang}/{device_id}/{channel}
```
Channel yang digunakan:
- `telemetry` (QoS 1, non-retain, interval 5 detik): skema `kampus.telemetry.v1` dengan metrics `power_w` (Watt) dan `energy_kwh` (kWh kumulatif non-menurun).
- `status` (QoS 1, retain + LWT): skema `kampus.status.v1` (`online` saat birth / `offline` via LWT).
- `heartbeat` (QoS 0, interval 15 detik): status `"alive"`.
- `cmd` (QoS 1): perintah ganti mode injektor secara dinamis (`set_mode`).

### 4 Perangkat kWh Meter (Gedung `bsd-a`, Lantai 3)

| Device ID | Gedung | Ruang | Jenis | Display Name | Topik Telemetri |
|---|---|---|---|---|---|
| `kwh-01` | `bsd-a` | `r3012` | `kwh-meter` | KWh Meter Ruang 3012 | `kampus/energy/bsd-a/r3012/kwh-01/telemetry` |
| `kwh-02` | `bsd-a` | `r3013` | `kwh-meter` | KWh Meter Ruang 3013 | `kampus/energy/bsd-a/r3013/kwh-02/telemetry` |
| `kwh-03` | `bsd-a` | `r3017` | `kwh-meter` | KWh Meter Ruang 3017 | `kampus/energy/bsd-a/r3017/kwh-03/telemetry` |
| `kwh-04` | `bsd-a` | `lab-iot` | `kwh-meter` | KWh Meter Lab IoT | `kampus/energy/bsd-a/lab-iot/kwh-04/telemetry` |

---

## 4. Asumsi Sistem, Ambang Batas & Endpoint API

- **Tarif Simulasi:** **Rp 1.500 / kWh** *(asumsi simulasi internal kampus, bukan tarif resmi PLN)*.
- **Jam Kerja Acuan:** Senin–Jumat, pukul **07.00–18.00 WIB**.
- **Aturan Bisnis & Alert (`Rules - Smart Energy`):**
  - `WASTE_AFTER_HOURS` (`warning`): `power_w > 200 W` di luar jam kerja selama **>= 2 menit** (120 detik).
  - `HIGH_LOAD` (`critical`): `power_w > 3000 W` selama **>= 1 menit** (60 detik), baik dalam maupun luar jam kerja.
  - `OFFLINE` (`critical`): tidak ada telemetri/heartbeat selama **>= 60 detik** atau status LWT `offline`.
  - Dilengkapi **deduplikasi** (anti-spam alert) dan **auto-resolve** ketika kondisi kembali normal.
- **Endpoint REST API Smart Energy (`/api/v1/energy/*`, wajib header `X-API-Key`):**
  - `GET /api/v1/energy/rooms` — status live, daya terakhir (W), dan kWh tiap ruang.
  - `GET /api/v1/energy/rooms/{ruang}/usage?from=&to=` — deret waktu & ringkasan pemakaian ruang.
  - `GET /api/v1/energy/rooms/{ruang}/usage/export?from=&to=` — ekspor riwayat pemakaian ke **CSV**.
  - `GET /api/v1/energy/waste?from=&to=` — rekap kejadian pemborosan luar jam kerja & status ACK.
  - `GET /api/v1/energy/bill?period=daily|weekly` — estimasi tagihan simulasi (memuat `tarif_asumsi` & `periode`).
  - `GET /api/v1/energy/baseline?from=&to=` — perbandingan rata-rata beban jam kerja vs luar jam kerja.
  - `POST /api/v1/alerts/{alert_id}/ack` — konfirmasi penanganan alert (*idempotent*).

> **Keamanan & Secret:** Berkas `.env` berisi kredensial sungguhan tidak pernah di-commit ke Git. Gunakan template `.env.example` sebagai acuan konfigurasi.

---

## 5. Cara Menjalankan Sistem (Reproduksi)

### A. Prasyarat
- Windows 10/11 dengan **Docker Desktop** (WSL 2 backend aktif).
- Git dan Python 3.11+ (opsional jika menjalankan skrip injektor/test lokal).

### B. Langkah Menjalankan
1. Clone repositori dan pindah ke branch `team-1-energy`:
   ```bash
   git clone https://github.com/wanlubis/iotkampus-tim3-air24.git
   cd iotkampus-tim3-air24
   git checkout team-1-energy
   ```
2. Siapkan berkas `.env` dari `.env.example` dan isi variabel yang masih kosong:
   ```bash
   cp .env.example .env
   ```
3. Jalankan platform beserta simulator Smart Energy (`profile team-1`):
   ```bash
   docker compose --profile team-1 up --build -d
   ```
4. Buka antarmuka di browser:
   - **Dashboard BMS Smart Energy**: [http://localhost:8080](http://localhost:8080) → pilih tab **Smart Energy**
   - **REST API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Grafana Observability**: [http://localhost:3000](http://localhost:3000)
   - **Node-RED Flow**: [http://localhost:1880](http://localhost:1880)

### C. Pengujian Keamanan API (`X-API-Key`)
```bash
# Tanpa token -> wajib 401 Unauthorized
curl -i http://localhost:8000/api/v1/energy/rooms

# Dengan token valid -> 200 OK
curl -i -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/energy/rooms
```

### D. Menghentikan Layanan
```bash
docker compose --profile team-1 down
```
*(Hindari `docker compose down -v` agar data persisten di InfluxDB dan PostgreSQL tidak terhapus.)*

---

## 6. Skenario Demo, Dashboard BMS & Unit Test Tim 1

### A. Injektor Gangguan (`simulators/energy/inject.py`)
1. **Pemborosan Luar Jam Kerja (`BOROS` → `WASTE_AFTER_HOURS`)**:
   ```bash
   python simulators/energy/inject.py boros --device kwh-02 --via cmd
   ```
   *Hasil:* Daya naik `> 200 W` (flag simulasi luar jam kerja); setelah 2 menit, alert `WASTE_AFTER_HOURS` (`warning`) muncul di dashboard & `/api/v1/energy/waste`.
2. **Lonjakan Beban Tinggi (`LONJAKAN` → `HIGH_LOAD`)**:
   ```bash
   python simulators/energy/inject.py lonjakan --device kwh-03 --via cmd
   ```
   *Hasil:* Daya melonjak `> 3000 W`; setelah 1 menit, alert `HIGH_LOAD` (`critical`) muncul di dashboard.
3. **Putus Mendadak / LWT (`CRASH` → `OFFLINE`) & No-Data (`STOP` → `OFFLINE` 60 dtk)**:
   ```bash
   python simulators/energy/inject.py crash --device kwh-01 --via cmd
   python simulators/energy/inject.py stop --device kwh-04 --via cmd
   ```
4. **Pulihkan Kondisi Normal (*Auto-Resolve*)**:
   ```bash
   python simulators/energy/inject.py normal --device all --via cmd
   ```

### B. Fitur Dashboard BMS Smart Energy (`http://localhost:8080`)
- **4 Kartu KPI Utama:** Daya Aktif Gedung, Energi Periode, Estimasi Tagihan, dan Boros Belum ACK.
- **Interactive 2D Architectural Floor Plan (SVG):** Denah top-down Lantai 3 Gedung BSD-A (`R3012`, `R3013`, `R3017`, `Lab-IoT`) dengan *heatmap* status dinamis (`Normal`, `Waste`, `High-Load`, `Offline`) dan nilai Watt real-time.
- **Grafik Analitik Permanen & Panel Detail:** Grafik **Tren Daya**, **Distribusi Tagihan**, **Panel Detail Ruangan** tersinkronisasi, **Alert & Status Anomali** dengan tombol **Tandai ACK**, **Baseline Jam Kerja**, **Tabel kWh Meter**, **Ekspor CSV**, serta tombol **Mode Simulasi** untuk pratinjau lokal.

### C. Unit Test Terotomasi Tim 1
```bash
pytest -q api/tests/test_energy_api.py simulators/energy/test_simulator.py
node nodered/tests/test_rules.js
```
