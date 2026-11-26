# Mini IoT Platform Kampus (AIR24)
**CSEB3073 IoT Cloud & Backend · Semester Ganjil 2026/2027 · Universitas Prasetiya Mulya**

Repository monorepo resmi untuk **Mini IoT Platform Kampus**, mengintegrasikan tiga domain utama dalam satu kesatuan sistem:
1. **Smart Energy (Tim 1)** — Simulasi 4 kWh meter per ruang, deteksi pemborosan, estimasi tagihan, dan 2D SVG BMS floorplan.
2. **Cold-Chain / Smart Storage (Tim 2)** — Suhu penyimpanan vaksin/reagen, kelembapan, status pintu, eskalasi alert bertingkat, dan kontrol setpoint downlink MQTT.
3. **Smart Environment / Air Quality (Tim 3 & Wali Integrasi)** — Pemantauan CO₂, PM2.5, kebisingan, orkestrasian Docker Compose, autentikasi REST API, dan Central Dashboard 3 domain.

---

## 1. Pembagian Peran Anggota Kelas (7 Mahasiswa — 3 Tim)

### Tim 3: Smart Environment & Wali Integrasi Lintas Domain
| Nama Anggota | Kontak GitHub | Peran Utama | Folder Tanggung Jawab |
|---|---|---|---|
| **Alwan Aqthin** | `wanlubis` (`alwanatqhinlubis18@gmail.com`) | **Koordinator Integrasi**: Compose, Keamanan, Registry Master, Core API (`/summary`), Central Dashboard | `docker-compose.yml`, `postgres/`, `api/app/routers/core.py`, `dashboard/` |
| **Marina Evelin** | `marinaevelin02@gmail.com` | Owner Router FastAPI Domain Air, Integrasi API, Visualisasi Metrik Ruang | `api/app/routers/air.py`, `dashboard/` |
| **Herlina Wulandari Dewi** | `herlinawulandarii22@gmail.com` | Owner Simulator Sensor Air Quality, Injektor Gangguan, Rule Engine Node-RED | `simulators/air/`, `nodered/` |

### Tim 1: Smart Energy
| Nama Anggota | Kontak GitHub | Peran Utama | Folder Tanggung Jawab |
|---|---|---|---|
| **Vincent (`VozzyJun`)** | `vincentjunio1@gmail.com` | Owner Simulator 4 kWh Meter, Injektor Gangguan, & Rule Engine Energy Node-RED | `simulators/energy/`, `nodered/` (tab `Rules - Smart Energy`) |
| **Aldy (`Aldy-create`)** | `aldypasaribu59@gmail.com` | Owner REST API Smart Energy (`/api/v1/energy/*`), Tab Dashboard Smart Energy (BMS 2D SVG Floor Plan), Panel Grafana, & Unit Test | `api/app/routers/energy.py`, `api/tests/test_energy_api.py`, `dashboard/energy/`, `grafana/` |

### Tim 2: Cold-Chain / Smart Storage
| Nama Anggota | Kontak GitHub | Peran Utama | Folder Tanggung Jawab |
|---|---|---|---|
| **Ericson Meo (`ericsonmeo`)** | `eriksonmeo@gmail.com` | Owner Simulator 3 Chamber Cold-Chain, Injektor Gangguan (SPIKE, DOOR, CRASH), Downlink CMD Setpoint | `simulators/coldchain/`, `simulator.py` |
| **Chandra Jazzel (`cazzel`)** | `chandrajazzel@gmail.com` | Owner Rule Engine Eskalasi Bertingkat, REST API Cold-Chain (`/api/v1/coldchain/*`), & UI Chamber Cold-Chain | `api/app/routers/coldchain.py`, `nodered/` (tab `Rules - Cold-Chain`), `dashboard/` |

---

## 2. Arsitektur & Daftar Layanan (Docker Compose)

Platform berjalan secara lokal dan gratis menggunakan Docker Compose pada laptop Windows (WSL2):

| Layanan | Port Host | URL / Endpoint | Keterangan |
|---|---|---|---|
| **mosquitto** | 1883 | `mqtt://localhost:1883` | Eclipse Mosquitto MQTT Broker (Autentikasi User/Password aktif, `allow_anonymous false`) |
| **nodered** | 1880 | `http://localhost:1880` | Ingest data, validasi skema, rule engine terpisah per tab domain |
| **influxdb** | 8086 | `http://localhost:8086` | InfluxDB 2 (Bucket: `iot`, Org: `prasmul`) time-series storage |
| **postgres** | 5432 | `localhost:5432` | PostgreSQL 16 (DB: `kampus`) untuk data master `devices` & `alert_events` |
| **api** | 8000 | `http://localhost:8000` | FastAPI Backend & REST API (OpenAPI docs di `/docs`, auth `X-API-Key`) |
| **dashboard** | 8080 | `http://localhost:8080` | Central Dashboard HTML/CSS/JS Pusat Lintas 3 Domain via Nginx |
| **grafana** | 3000 | `http://localhost:3000` | Observability & visualisasi operasional ketiga domain |
| **air-simulator** | - | Background Service | Simulator node `aq-01`, `aq-02`, `aq-03` |
| **energy-simulator** | - | Profile `team-1` | Simulator meter `kwh-01` s.d. `kwh-04` |
| **coldchain-simulator**| - | Profile `team-2` | Simulator chamber `cc-01` s.d. `cc-03` |

---

## 3. Peta Topic MQTT & 10 Perangkat Wajib Minimum

### Konvensi Topic (Bagian 4.1)
```text
kampus/{domain}/{gedung}/{ruang}/{device_id}/{channel}
```
* **Domain yang diizinkan**: `energy` | `coldchain` | `air`
* **Channel**: `telemetry` (QoS 1), `status` (QoS 1, retain + LWT), `heartbeat` (QoS 0/1), `cmd` (QoS 1).

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

Semua angka ambang berikut adalah asumsi simulasi lab kampus:

1. **Smart Environment / Air Quality (Tim 3)**:
   - `CO2_HIGH`: Warning jika `co2_ppm > 1000 ppm`; Critical jika `co2_ppm > 1500 ppm`.
   - `PM25_HIGH`: Warning jika `pm25_ugm3 > 35 µg/m³`; Critical jika `pm25_ugm3 > 75 µg/m³`.
   - `NOISE_HIGH`: Warning jika `noise_db > 70 dB`.
   - `OFFLINE`: Critical jika telemetry/heartbeat terputus 60 detik atau LWT bernilai offline.

2. **Cold-Chain (Tim 2)**:
   - `TEMP_WARN`: Warning jika `temp_c > 6.0 °C` selama 60 detik.
   - `TEMP_HIGH`: Critical jika `temp_c > 8.0 °C` selama 120 detik.
   - `TEMP_ESCALATED`: Severity `escalated` jika `TEMP_HIGH` belum di-ACK dalam 5 menit.
   - `DOOR_OPEN_LONG`: Warning jika `door_open = true` selama 60 detik.
   - `BATTERY_LOW`: Warning jika `battery_pct < 20%`.
   - `OFFLINE`: Critical jika telemetry/heartbeat terputus 60 detik atau LWT bernilai offline.

3. **Smart Energy (Tim 1)**:
   - Tarif simulasi: **Rp 1.500 / kWh** (Asumsi internal kampus, bukan tarif resmi PLN).
   - Jam kerja acuan: Senin–Jumat, 07.00–18.00 WIB.
   - `WASTE_AFTER_HOURS`: Warning jika `power_w > 200 W` di luar jam kerja selama 2 menit.
   - `HIGH_LOAD`: Critical jika `power_w > 3000 W` selama 1 menit.

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
3. Bangun dan jalankan seluruh service platform (termasuk simulator Tim 1 & Tim 2):
   ```bash
   docker compose --profile team-1 --profile team-2 up --build -d
   ```
4. Buka antarmuka di browser:
   - **Central Dashboard (3 Domain)**: [http://localhost:8080](http://localhost:8080)
   - **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Grafana Observability**: [http://localhost:3000](http://localhost:3000)
   - **Node-RED Console**: [http://localhost:1880](http://localhost:1880)

### C. Menguji Keamanan & Kontrak API Bersama
1. **Health Check (Tanpa Token)**:
   ```bash
   curl -i http://localhost:8000/health
   ```
2. **Uji Keamanan API (Wajib 401 jika tanpa header `X-API-Key`)**:
   ```bash
   curl -i http://localhost:8000/api/v1/summary
   # Output: HTTP/1.1 401 Unauthorized {"error": {"code": "UNAUTHORIZED", ...}}
   ```
3. **Uji Kontrak `/summary` dengan API Key Benar**:
   ```bash
   curl -i -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/summary
   ```

### D. Perintah Menghentikan Sistem
```bash
docker compose down
```

---

## 6. Skenario Demo & Injektor Gangguan (Bagian 11)

### A. Domain Smart Energy (Tim 1)
```bash
# Injeksi pemborosan di luar jam kerja (>200 W):
python simulators/energy/simulator.py --mode BOROS

# Injeksi lonjakan beban kritis (>3000 W):
python simulators/energy/simulator.py --mode LONJAKAN
```

### B. Domain Cold-Chain (Tim 2)
```bash
# Injeksi lonjakan suhu kritis (>8 °C):
python simulators/coldchain/simulator.py --mode SPIKE

# Injeksi pintu terbuka lama (>60 detik):
python simulators/coldchain/simulator.py --mode DOOR

# Uji Crash / LWT Offline (cc-01):
python simulators/coldchain/simulator.py --mode CRASH --device cc-01

# Kontrol Setpoint Downlink CMD (via API):
curl -X POST -H "X-API-Key: YOUR_API_KEY" -H "Content-Type: application/json" \
  -d '{"command": "setpoint", "args": {"temp_c": 3.2}}' \
  http://localhost:8000/api/v1/coldchain/cmd/cc-01
```

### C. Domain Smart Environment (Tim 3)
```bash
# Injeksi lonjakan CO2 (>1500 ppm):
python simulators/air/simulator.py --mode CO2_SPIKE --device aq-01

# Injeksi lonjakan partikulat debu PM2.5 (>75 µg/m³):
python simulators/air/simulator.py --mode PM_SPIKE --device aq-02

# Injeksi kebisingan (>70 dB):
python simulators/air/simulator.py --mode NOISE_SPIKE --device aq-03

# Uji Crash / LWT Offline (aq-01):
python simulators/air/simulator.py --mode CRASH --device aq-01
```
