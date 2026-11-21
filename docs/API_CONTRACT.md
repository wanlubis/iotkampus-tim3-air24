# API Integration Contract â€” Mini IoT Platform Kampus (AIR24)
**Wali Integrasi: Tim 3**

Dokumen ini mendefinisikan kontrak REST API resmi untuk antarmuka dashboard, integrasi lintas domain, dan evaluasi pengujian.

---

## 1. Konvensi Dasar
- **Base URL:** `http://localhost:8000`
- **Interactive Documentation:** `http://localhost:8000/docs` (Swagger UI) dan `http://localhost:8000/redoc`
- **Zona Waktu:** Semua atribut waktu pada respons API berformat **ISO 8601 dengan offset +07:00 (WIB / Asia/Jakarta)**.
- **Format Error Seragam (Bagian 4.6):**
  ```json
  {
    "error": {
      "code": "UNAUTHORIZED | NOT_FOUND | VALIDATION_ERROR | CONFLICT | INTERNAL",
      "message": "Deskripsi kesalahan teknis yang ramah pengguna"
    }
  }
  ```

---

## 2. Autentikasi
Seluruh endpoint di bawah `/api/v1/` wajib menyertakan HTTP Header:
```http
X-API-Key: YOUR_API_KEY
```
*Catatan:* Jika header tidak dikirim atau nilainya salah, API menjawab status `401 Unauthorized` dengan error code `UNAUTHORIZED`. Endpoint `GET /health` adalah satu-satunya rute publik yang tidak memerlukan header token.

---

## 3. Endpoint Bersama (Core & Integration)

### A. Health Check (Tanpa Token)
- **Method & Path:** `GET /health`
- **Fungsi:** Memeriksa kesehatan layanan API.
- **Contoh Respons (200 OK):**
  ```json
  {
    "status": "healthy",
    "waktu": "2026-11-21T01:30:00.000000+07:00",
    "versi": "1.0.0",
    "platform": "Mini IoT Platform Kampus AIR24",
    "wali_integrasi": "Tim 3"
  }
  ```

### B. Summary Lintas Domain (Kontrak Wajib Bagian 7.5)
- **Method & Path:** `GET /api/v1/summary`
- **Fungsi:** Digunakan dashboard pusat untuk menyatukan status perangkat online, active alert, dan KPI ringkas dari 3 domain tanpa query parsial.
- **Contoh Respons (200 OK):**
  ```json
  {
    "generated_at": "2026-11-21T01:30:00+07:00",
    "devices": { "total": 10, "online": 10, "offline": 0 },
    "alerts_active": { "warning": 0, "critical": 0, "escalated": 0 },
    "domains": {
      "energy": { "devices_online": 4, "devices_total": 4, "kpi": { "name": "power_w_total", "value": 4120.0, "unit": "W" }, "alerts_active": 0 },
      "coldchain": { "devices_online": 3, "devices_total": 3, "kpi": { "name": "temp_c_max", "value": 3.8, "unit": "Â°C" }, "alerts_active": 0 },
      "air": { "devices_online": 3, "devices_total": 3, "kpi": { "name": "co2_ppm_max", "value": 650.0, "unit": "ppm" }, "alerts_active": 0 }
    }
  }
  ```

### C. Registry Perangkat Kampus
- `GET /api/v1/devices` : Mengambil daftar seluruh perangkat (Filter: `domain`, `gedung`, `ruang`, `is_active`). Mengembalikan status online/offline live.
- `GET /api/v1/devices/{device_id}` : Detail registry 1 perangkat (404 jika tidak ditemukan).
- `GET /api/v1/devices/{device_id}/status` : Membaca status ketersediaan terkini dari InfluxDB measurement `status`.

### D. Telemetri
- `GET /api/v1/telemetry` : Riwayat telemetri time-series dari InfluxDB (Filter: `domain`, `device_id`, `from`, `to`, `limit`).
- `GET /api/v1/telemetry/latest` : Titik metrik terakhir per perangkat aktif.

### E. Alert & ACK
- `GET /api/v1/alerts` : Riwayat alert kejadian (Filter: `domain`, `severity`, `acked`, `limit`).
- `GET /api/v1/alerts/{alert_id}` : Detail 1 alert (404 jika tidak ditemukan).
- `POST /api/v1/alerts/{alert_id}/ack` : Menandai status ACK pada alert. Body opsional: `{"acked_by": "Nama Operator"}`. Idempoten jika sudah di-ACK.
- `POST /api/v1/alerts` : Ingestion alert dari Node-RED / simulator.

---

## 4. Endpoint Domain Khusus

### A. Smart Environment (Tim 3)
- `GET /api/v1/air/rooms` : Daftar ruang + metrik CO2, PM2.5, Noise terakhir + status.
- `GET /api/v1/air/rooms/{ruang}` : Detail satu ruangan + histori ringkas.

### B. Cold-Chain (Tim 2)
- `GET /api/v1/coldchain/chambers` : Daftar 3 chamber + suhu/pintu/setpoint.
- `GET /api/v1/coldchain/chambers/{device_id}` : Detail satu chamber.
- `GET /api/v1/coldchain/escalations` : Alert yang sedang dalam eskalasi bertingkat.
- `POST /api/v1/coldchain/cmd/{device_id}` : Mengirim perintah setpoint suhu baru (`temp_c`).

### C. Smart Energy (Tim 1)
- `GET /api/v1/energy/rooms` : Daftar ruang + daya Watt terakhir + kumulatif kWh.
- `GET /api/v1/energy/rooms/{ruang}/usage` : Profil pemakaian daya ruang tertentu.
- `GET /api/v1/energy/waste` : Rekap kejadian pemborosan energi di luar jam kerja.
- `GET /api/v1/energy/bill?period=daily|weekly` : Estimasi tagihan simulasi listrik.
