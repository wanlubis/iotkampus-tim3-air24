# Naskah Skenario Demo UAS (Runbook) — Tim 3 (AIR24)
**CSEB3073 IoT Cloud & Backend · Durasi: 25–30 Menit**

Gunakan panduan ini saat sesi live demo bersama dosen penguji (Syafrudi, M.Eng.).

---

## Persiapan Sebelum Demo (H-15 Menit)
1. Buka Docker Desktop di Windows.
2. Jalankan sistem dari root folder:
   ```bash
   docker compose up --build -d
   ```
3. Buka tab-tab browser berikut di layar proyektor / sharing:
   - **Tab 1: Dashboard Pusat** -> `http://localhost:8080`
   - **Tab 2: Swagger OpenAPI** -> `http://localhost:8000/docs`
   - **Tab 3: Grafana Dashboard** -> `http://localhost:3000` (User: `admin` / `admin`)
   - **Tab 4: Node-RED Flow** -> `http://localhost:1880`
4. Buka terminal PowerShell untuk injeksi gangguan.

---

## Alur Naskah Demo (Bagian 11)

### 1. Menit 0–2: Berdiri di Arsitektur
- **Juru Bicara Tim 3**: Memperkenalkan anggota tim dan menjelaskan peran Tim 3 (Smart Environment + Wali Integrasi).
- **Penjelasan**: Tunjukkan diagram arsitektur:
  - 10 sensor mengirim ke **Mosquitto** (port 1883) dengan user/password.
  - **Node-RED** (port 1880) memvalidasi payload JSON dan meneruskan ke basis data.
  - Telemetri masuk ke **InfluxDB 2** (`prasmul/iot`), master registry & alerts masuk ke **PostgreSQL 16** (`kampus`).
  - **FastAPI** (port 8000) menyediakan endpoint REST dengan pengamanan `X-API-Key`.
  - Satu **Dashboard Pusat** (port 8080) dan **Grafana** (port 3000) menampilkan operasi sistem.

### 2. Menit 2–6: Jalur Bahagia (Happy Path)
- Buka **Dashboard Pusat (port 8080)**:
  - Tunjukkan **10 perangkat terdaftar dan status ONLINE**.
  - Tunjukkan data telemetri bergerak otomatis (auto-refresh 5 detik tanpa reload halaman).
  - Tunjukkan tab **Smart Environment (Air)**: nilai CO2, PM2.5, dan Noise live dari 3 ruangan (`r3012`, `r3017`, `koridor-1`).
  - Tunjukkan tab **Cold-Chain** dan **Smart Energy**.
- Buka **Grafana (port 3000)**: Tunjukkan laju pesan MQTT dan timeline status hidup.

### 3. Menit 6–8: Pembuktian Keamanan API
Buka terminal PowerShell dan jalankan:
1. Panggil API tanpa header token:
   ```bash
   curl -i http://localhost:8000/api/v1/summary
   ```
   *Ekspektasi:* HTTP Status **401 Unauthorized** dengan body:
   `{"error": {"code": "UNAUTHORIZED", "message": "X-API-Key tidak valid"}}`
2. Panggil API dengan header token yang benar:
   ```bash
   curl -i -H "X-API-Key: wanganteng" http://localhost:8000/api/v1/summary
   ```
   *Ekspektasi:* HTTP Status **200 OK**, data ringkasan 3 domain lengkap sesuai kontrak Bagian 7.5.

### 4. Menit 8–12: Gangguan Tim 1 (Energy)
- Picu simulasi boros atau beban tinggi di domain energy.
- Perhatikan alert muncul di feed gabungan dasbor pusat. Tekan tombol **ACK** di dashboard.

### 5. Menit 12–17: Gangguan Tim 2 (Cold-Chain)
- Uji kenaikan suhu chamber hingga `TEMP_HIGH`.
- Uji **CRASH** satu chamber:
  - Putus socket MQTT secara mendadak.
  - Tunjukkan broker Mosquitto menerbitkan Last Will and Testament (LWT) `offline`.
  - State chamber berubah menjadi Offline di dashboard dan InfluxDB.
  - Hubungkan kembali (Reconnect) untuk memulihkan.

### 6. Menit 17–20: Gangguan Tim 3 (Smart Environment) & Uji Ketahanan Lintas Domain
Jalankan di terminal simulator Tim 3:
1. **Picu Lonjakan CO2 (CO2_SPIKE)**:
   ```bash
   python simulators/air/simulator.py --mode CO2_SPIKE --device aq-01
   ```
   *Hasil:* Nilai CO2 di ruang `r3012` melesat >1500 ppm. Banner / indikator berubah menjadi Merah (Critical), alert `CO2_HIGH` terbit di feed alert gabungan.
2. **Buktikan Isolasi Gangguan (Fault Isolation)**:
   - Tunjukkan bahwa meskipun node `aq-01` mengalami lonjakan kritis, domain Cold-Chain dan Smart Energy **tetap hidup normal** tanpa terganggu.
3. **Lakukan ACK**:
   - Klik tombol **Tandai ACK** di feed alert dasbor pusat. Status alert berubah menjadi "Di-ACK oleh operator".

### 7. Menit 20–22: Penutup Teknis
- Tunjukkan struktur repositori monorepo di VS Code / file explorer.
- Tunjukkan berkas `.env.example` dan tegaskan bahwa `.env` tidak pernah di-commit ke Git.
- Tunjukkan berkas kontrak `docs/MQTT_CONTRACT.md` dan `docs/API_CONTRACT.md`.

### 8. Menit 22–30: Tanya Jawab Individu (Q&A)
- Setiap anggota menjawab pertanyaan teknis seputar peran dan folder tanggung jawabnya.
