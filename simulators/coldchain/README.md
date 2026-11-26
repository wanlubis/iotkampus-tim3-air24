# Simulator Cold-Chain / Smart Storage (Tim 2)

Simulator resmi untuk **3 chamber** (`cc-01`, `cc-02`, `cc-03`) domain **Cold-Chain** (Universitas Prasetiya Mulya — AIR24).

---

## 1. Spesifikasi Perangkat & Ruang (Bagian 6.2)

| Device ID | Gedung | Ruang | Deskripsi | Base Temp | Setpoint Awal |
|---|---|---|---|---|---|
| `cc-01` | bsd-a | gudang-a | Chamber Vaksin Utama | 4.5 °C | 4.5 °C |
| `cc-02` | bsd-a | gudang-a | Chamber Sampel Darah | 3.8 °C | 3.8 °C |
| `cc-03` | bsd-a | gudang-b | Chamber Reagen Kimia | 5.2 °C | 5.2 °C |

---

## 2. Topic MQTT & Channel

* **Telemetry (QoS 1)**: `kampus/coldchain/bsd-a/{ruang}/{device_id}/telemetry` (interval 5 detik)
* **Status (QoS 1, retain=True + LWT)**: `kampus/coldchain/bsd-a/{ruang}/{device_id}/status`
* **Heartbeat (QoS 1)**: `kampus/coldchain/bsd-a/{ruang}/{device_id}/heartbeat` (interval 15 detik)
* **Command Downlink (QoS 1)**: `kampus/coldchain/bsd-a/{ruang}/{device_id}/cmd`

---

## 3. Cara Menjalankan Simulator

### A. Melalui Docker Compose
```bash
docker compose --profile team-2 up --build -d
```

### B. Menjalankan Langsung via Python (Lokal)
```bash
cd simulators/coldchain
pip install -r requirements.txt
python simulator.py --mode NORMAL
```

---

## 4. Mode Pengujian & Injeksi Gangguan (Demo Skenario Bagian 11)

Dapat dipicu saat program berjalan dengan mengetik perintah di prompt `Mode>` atau via argumen CLI:

1. **Mode NORMAL**: Suhu stabil di sekitar setpoint, pintu tertutup (`door_open: false`).
   ```bash
   python simulator.py --mode NORMAL
   ```
2. **Mode SPIKE**: Suhu melonjak naik &gt;6°C (`TEMP_WARN`) hingga &gt;8°C (`TEMP_HIGH`).
   ```bash
   python simulator.py --mode SPIKE
   # Atau ketik SPIKE di terminal simulator
   ```
3. **Mode DOOR**: Pintu terbuka terus menerus selama &gt;60 detik (`DOOR_OPEN_LONG`).
   ```bash
   python simulator.py --mode DOOR
   ```
4. **Mode STOP (Uji No-Data)**: Menghentikan pengiriman telemetri namun status tetap online (menguji deteksi no-data timeout 60s).
   ```bash
   python simulator.py --mode STOP
   ```
5. **Mode CRASH (Uji LWT Offline)**: Memutuskan soket TCP secara mendadak sehingga broker mem-publish LWT offline.
   ```bash
   python simulator.py --mode CRASH --device cc-01
   # Atau ketik CRASH cc-01 di terminal simulator
   ```
6. **Perintah RECONNECT**: Memulihkan chamber yang sebelumnya mengalami crash:
   ```text
   RECONNECT cc-01
   ```

---

## 5. Menerima Perintah Setpoint (Downlink)

Simulator berlangganan topic `cmd` dan secara otomatis memperbarui setpoint saat menerima perintah dari API (`POST /api/v1/coldchain/cmd/{device_id}`):
```json
{
  "command": "setpoint",
  "args": {
    "temp_c": 3.5
  }
}
```
Hasil setpoint baru akan langsung tercermin pada field `setpoint_c` di telemetri berikutnya.
