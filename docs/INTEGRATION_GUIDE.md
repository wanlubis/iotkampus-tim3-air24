\# Integration Guide

\## IoT Kampus AIR24



Dokumen ini menjadi panduan bagi Team 1 (Energy), Team 2 (Cold Chain), dan Team 3 (Air Quality) untuk mengintegrasikan sistem masing-masing ke platform IoT Kampus AIR24.



\## 1. Arsitektur Sistem



Setiap tim mengembangkan simulator atau perangkat IoT sesuai domain masing-masing.



Seluruh data dikirim melalui MQTT Broker pusat dan diproses oleh Node-RED.



Alur sistem:



Simulator / Device → MQTT Broker → Node-RED → InfluxDB / PostgreSQL → FastAPI → Central Dashboard.



\## 2. Tanggung Jawab Setiap Tim



| Tim | Domain | Tanggung Jawab |

|---|---|---|

| Team 1 | Energy | Simulator dan telemetry energi |

| Team 2 | Cold Chain | Simulator dan telemetry cold chain |

| Team 3 | Air Quality | Simulator kualitas udara dan integrasi platform |



\## 3. File yang Harus Disediakan



Setiap tim wajib menyediakan:



\- Source code simulator atau firmware.

\- `requirements.txt` jika menggunakan Python.

\- `Dockerfile` jika simulator dijalankan dalam container.

\- Daftar device ID.

\- MQTT topic yang digunakan.

\- Contoh payload JSON.

\- Daftar metrics dan satuannya.

\- Instruksi menjalankan simulator.



\## 4. MQTT Connection



Semua simulator harus menggunakan konfigurasi berikut:



\- MQTT Host: `mosquitto`

\- MQTT Port: `1883`

\- MQTT Username: menggunakan kredensial dari pengelola platform.

\- MQTT Password: menggunakan kredensial dari pengelola platform.



Jangan menggunakan `localhost` sebagai host MQTT di dalam container Docker.



\## 5. MQTT Topic



Gunakan format:



`kampus/{domain}/{gedung}/{ruang}/{device\_id}/{channel}`



Domain:

\- `energy`

\- `coldchain`

\- `air`



Channel:

\- `telemetry`

\- `status`

\- `heartbeat`

\- `cmd`



Contoh:

`kampus/energy/gedung-a/ruang-101/en-01/telemetry`



\## 6. Format Telemetry



Gunakan format JSON dengan struktur utama berikut:



```json

{

&#x20; "device\_id": "en-01",

&#x20; "timestamp": "2026-11-20T10:00:00Z",

&#x20; "mode": "NORMAL",

&#x20; "metrics": {

&#x20;   "voltage": 220,

&#x20;   "current": 2.5,

&#x20;   "power": 550

&#x20; }

}

```



Nama metrics dapat disesuaikan dengan domain masing-masing.



\## 7. Docker Integration



Jika simulator menggunakan Python, tim harus menyediakan Dockerfile.



Contoh konfigurasi service pada Docker Compose utama:



```yaml

energy-simulator:

&#x20; build:

&#x20;   context: ./simulators/energy

&#x20; environment:

&#x20;   MQTT\_HOST: mosquitto

&#x20;   MQTT\_PORT: 1883

&#x20;   MQTT\_USERNAME: ${MQTT\_USERNAME}

&#x20;   MQTT\_PASSWORD: ${MQTT\_PASSWORD}

&#x20; depends\_on:

&#x20;   - mosquitto

&#x20; restart: unless-stopped

```



Team 3 akan menggabungkan konfigurasi setiap tim ke dalam `docker-compose.yml` utama.



Setiap tim tidak boleh menjalankan MQTT Broker sendiri untuk integrasi final.



\## 8. Integration Testing



Sebelum dinyatakan terintegrasi, setiap tim harus memastikan:



1\. Simulator berhasil dijalankan.

2\. Perangkat berhasil terhubung ke MQTT Broker.

3\. Telemetry berhasil diterima Node-RED.

4\. Format JSON sesuai kontrak.

5\. Data berhasil disimpan ke InfluxDB.

6\. Data dapat diakses melalui API dan dashboard pusat.



\## 9. Security



\- Jangan mengunggah file `.env`.

\- Jangan memb

