# Mini IoT Platform Kampus — Tim 3 (AIR24)
**CSEB3073 IoT Cloud & Backend · Semester Ganjil 2026/2027 · Universitas Prasetiya Mulya**

Repository monorepo resmi untuk **Mini IoT Platform Kampus**, dikelola oleh **Tim 3 (Smart Environment / Air Quality & Wali Integrasi Lintas Domain)**.

---

## 1. Pembagian Peran Anggota Tim 3

| Nama Anggota | Kontak GitHub | Peran Utama | Folder Tanggung Jawab |
|---|---|---|---|
| **Herlina Wulandari Dewi** | `herlinawulandarii22@gmail.com` | Simulator Sensor Air Quality, Injektor Gangguan, Rule Engine Node-RED | `simulators/air/`, `nodered/` |
| **Marina Evelin** | `marinaevelin02@gmail.com` | Router FastAPI Domain Air, Integrasi API, Visualisasi Metrik Ruang | `api/app/routers/air.py`, `dashboard/` |
| **Alwan Aqthin** | `alwanatqhinlubis18@gmail.com` | **Koordinator Integrasi**: Compose, Keamanan, Registry Master, Core API (`/summary`), Dashboard Pusat | `docker-compose.yml`, `postgres/`, `api/app/routers/core.py`, `dashboard/` |

### Pembagian Peran Anggota Tim 1 (Smart Energy)

| Nama Anggota | Kontak GitHub | Peran Utama | Folder Tanggung Jawab |
|---|---|---|---|
| **<Isi Nama Anggota 1>** | `<email/github-anggota-1>` | Owner Simulator 4 kWh Meter, Injektor Gangguan, & Rule Engine Energy Node-RED | `simulators/energy/`, `nodered/` (tab Energy) |
| **Aldy (`Aldy-create`)** | `aldypasaribu59@gmail.com` | Owner REST API Smart Energy (`/api/v1/energy/*`), Tab Dashboard Smart Energy, Panel Grafana, & Unit Test | `api/app/routers/energy.py`, `api/tests/test_energy_api.py`, `dashboard/` (`#content-energy`), `grafana/` |

---

## 2. Arsitektur & Daftar Layanan (Docker Compose)

Platform berjalan secara lokal dan gratis menggunakan Docker Compose pada laptop Windows (WSL2):

| Layanan | Port Host | URL / Endpoint | Keterangan |
|---|---|---|---|
| **mosquitto** | 1883 | `mqtt://localhost:1883` | Eclipse Mosquitto MQTT Broker (Autentikasi User/Password aktif) |
| **nodered** | 1880 | `http://localhost:1880` | Ingest data, validasi skema, rule engine ambang batas |
| **influxdb** | 8086 | `http://localhost:8086` | InfluxDB 2 (Bucket: `iot`, Org: `prasmul`) time-series storage |
| **postgres** | 5432 | `localhost:5432` | PostgreSQL 16 (DB: `kampus`) untuk data master `devices` & `alert_events` |
| **api** | 8000 | `http://localhost:8000` | FastAPI Backend & REST API (OpenAPI docs di `/docs`) |
| **dashboard** | 8080 | `http://localhost:8080` | Dashboard HTML/CSS/JS Pusat Lintas 3 Domain |
| **grafana** | 3000 | `http://localhost:3000` | Observability & visualisasi operasional (gunakan GRAFANA_ADMIN_USER dan GRAFANA_ADMIN_PASSWORD dari .env) |
| **air-simulator** | - | Background Service | Simulator node `aq-01`, `aq-02`, `aq-03` |

---

## 3. Peta Topic MQTT & Daftar Perangkat

### Konvensi Topic (Bagian 4.1)
```text
kampus/{domain}/{gedung}/{ruang}/{device_id}/{channel}
```
Channel yang digunakan: `telemetry` (QoS 1), `status` (QoS 1, retain + LWT), `heartbeat` (QoS 0/1), `cmd` (QoS 1).

### 10 Perangkat Wajib Minimum (Bagian 4.2)

| Device ID | Domain | Gedung | Ruang Acuan | Jenis | Display Name |
|---|---|---|---|---|---|
| `kwh-01` | energy | bsd-a | r3012 | kwh-meter | KWh Meter Ruang 3012 |
| `kwh-02` | energy | bsd-a | r3013 | kwh-meter | KWh Meter Ruang 3013 |
| `kwh-03` | energy | bsd-a | r3017 | kwh-meter | KWh Meter Ruang 3017 |
| `kwh-04` | energy | bsd-a | lab-iot | kwh-meter | KWh Meter Lab IoT |
| `cc-01` | coldchain | bsd-a | gudang-a | chamber | Chamber Vaksin Utama |
| `cc-02` | coldchain | bsd-a | gudang-a | chamber | Chamber Sampel Darah |
| `cc-03` | coldchain | bsd-a | gudang-b | chamber | Chamber Reagen Kimia |
| `aq-01` | air | bsd-a | r3012 | aq-node | Air Quality Monitor R3012 |
| `aq-02` | air | bsd-a | r3017 | aq-node | Air Quality Monitor R3017 |
| `aq-03` | air | bsd-a | koridor-1 | aq-node | Air Quality Monitor Koridor 1 |

---

## 4. Asumsi Ambang Batas & Tarif Simulasi

1. **Smart Environment / Air Quality (Tim 3)**:
   - `CO2_HIGH`: Warning jika `co2_ppm > 1000 ppm`; Critical jika `co2_ppm > 1500 ppm`.
   - `PM25_HIGH`: Warning jika `pm25_ugm3 > 35 µg/m³`; Critical jika `pm25_ugm3 > 75 µg/m³`.
   - `NOISE_HIGH`: Warning jika `noise_db > 70 dB`.
   - `OFFLINE`: Critical jika telemetry/heartbeat terputus 60 detik atau LWT bernilai offline.
2. **Cold-Chain (Tim 2)**:
   - `TEMP_WARN`: Warning jika `temp_c > 6.0 °C`.
   - `TEMP_HIGH`: Critical jika `temp_c > 8.0 °C`.
   - `TEMP_ESCALATED`: Escalated jika `TEMP_HIGH` tidak di-ACK dalam 5 menit.
3. **Smart Energy (Tim 1)**:
   - Tarif simulasi: **Rp 1.500 / kWh** (Asumsi internal kampus, **bukan tarif resmi PLN**).
   - Jam kerja acuan: Senin–Jumat, 07.00–18.00 WIB.
   - `WASTE_AFTER_HOURS`: Warning jika `power_w > 200 W` di luar jam kerja selama 2 menit.
   - `HIGH_LOAD`: Critical jika `power_w > 3000 W` selama 1 menit (dalam/luar jam kerja).
   - `OFFLINE`: Critical jika telemetry/heartbeat hilang 60 detik atau status LWT `offline`.
   - Endpoint API Tim 1 (`/api/v1/energy/*`): `GET /rooms`, `GET /rooms/{ruang}/usage?from=&to=`, `GET /rooms/{ruang}/usage/export`, `GET /waste?from=&to=`, `GET /bill?period=daily|weekly`, dan `GET /baseline`.

> **Pernyataan Secret & Keamanan**: File `.env` sungguhan dan secret tidak pernah di-commit ke repositori Git. Kredensial lab dikonfigurasi melalui berkas template `.env.example`.

---

## 5. Cara Menjalankan Sistem (Reproduksi)

### A. Prasyarat
- Windows 10/11 dengan Docker Desktop (WSL 2 backend aktif).
- Git.

### B. Langkah Menjalankan
1. Clone repositori:
   ```bash
   git clone https://github.com/wanlubis/iotkampus-tim3-air24.git
   cd iotkampus-tim3-air24
   ```
2. Siapkan file `.env`:
   ```bash
   cp .env.example .env
   ```
3. Isi seluruh variabel secret yang masih kosong di file `.env`, lalu bangun dan jalankan service default:
   ```bash
   docker compose up --build -d
   ```
4. Buka browser:
   - **Dashboard Pusat**: [http://localhost:8080](http://localhost:8080)
   - **REST API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Grafana**: [http://localhost:3000](http://localhost:3000) (Gunakan GRAFANA_ADMIN_USER dan GRAFANA_ADMIN_PASSWORD dari .env)
   - **Node-RED**: [http://localhost:1880](http://localhost:1880)

### C. Menguji API dengan cURL / PowerShell
1. Uji **Health Check** (Tanpa token API):
   ```bash
   curl -i http://localhost:8000/health
   ```
2. Uji **Keamanan Header X-API-Key** (Wajib 401 jika tanpa token):
   ```bash
   curl -i http://localhost:8000/api/v1/summary
   # Output HTTP/1.1 401 Unauthorized {"error": {"code": "UNAUTHORIZED", ...}}
   ```
3. Uji **Kontrak Ringkasan Lintas Domain** (Dengan API Key yang benar):
   ```bash
   curl -i -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/summary
   ```

### D. Perintah Menghentikan & Mereset Data
- Menghentikan container tanpa menghapus data persisten:

docker compose down

- Peringatan: Hindari penggunaan docker compose down -v karena perintah tersebut dapat menghapus volume Docker dan seluruh data persisten
yang tersimpan di dalamnya. Jangan gunakan perintah penghapusan volume pada lingkungan proyek yang berisi data penting.

---

## 6. Skenario Demo & Injektor Gangguan (Bagian 11)

Untuk demonstrasi live di depan dosen penguji, gunakan simulator injektor berikut:

1. **Uji Lonjakan CO2 (CO2_SPIKE)**:
   ```bash
   python simulators/air/simulator.py --mode CO2_SPIKE --device aq-01
   ```
   *Hasil:* Metrik CO2 naik >1500 ppm, alert `CO2_HIGH` muncul di dashboard pusat dan dapat di-ACK.

2. **Uji Lonjakan Debu PM2.5 (PM_SPIKE)**:
   ```bash
   python simulators/air/simulator.py --mode PM_SPIKE --device aq-02
   ```

3. **Uji Kebisingan (NOISE_SPIKE)**:
   ```bash
   python simulators/air/simulator.py --mode NOISE_SPIKE --device aq-03
   ```

4. **Uji Crash Socket / Last Will & Testament (CRASH)**:
   ```bash
   python simulators/air/simulator.py --mode CRASH --device aq-01
   ```
   *Hasil:* Simulator mati seketika, broker Mosquitto mem-publish LWT `offline`, status perangkat di dashboard berubah menjadi Offline.

5. **Uji No-Data (STOP)**:
   ```bash
   python simulators/air/simulator.py --mode STOP --device aq-01
   ```
   *Hasil:* Koneksi tetap online namun telemetri berhenti dikirim.
