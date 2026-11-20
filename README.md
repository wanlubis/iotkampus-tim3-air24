

\# Mini IoT Platform Kampus — Tim 3



\## 1. Deskripsi Proyek



Mini IoT Platform Kampus adalah proyek Internet of Things (IoT) untuk memantau kondisi lingkungan dan perangkat di area kampus secara terpusat.



Tim 3 bertanggung jawab pada domain \*\*Smart Environment / Air Quality\*\*, yaitu pemantauan kualitas udara dan kebisingan di beberapa ruangan kampus.



Selain itu, Tim 3 bertugas sebagai koordinator integrasi agar seluruh layanan dari tiga domain dapat berjalan dalam satu platform.



\## 2. Fitur Utama



\- Monitoring CO2 (ppm).

\- Monitoring PM2.5 (µg/m³).

\- Monitoring tingkat kebisingan (dB).

\- Simulator perangkat kualitas udara.

\- Deteksi kondisi udara yang melewati ambang batas.

\- Notifikasi atau alert kondisi lingkungan.

\- Dashboard pusat untuk memantau seluruh domain.

\- Integrasi layanan menggunakan Docker Compose.



\## 3. Teknologi yang Digunakan



| Teknologi | Fungsi |

|---|---|

| Python | Simulator perangkat |

| Mosquitto MQTT | Komunikasi antarperangkat |

| Node-RED | Pengolahan data dan rule engine |

| InfluxDB 2 | Penyimpanan data time-series |

| PostgreSQL | Penyimpanan data master |

| FastAPI | REST API |

| HTML, CSS, JavaScript | Dashboard |

| Grafana | Monitoring dan visualisasi |

| Docker Compose | Menjalankan seluruh layanan |



\## 4. Struktur Repository



```text

iotkampus-tim3-air24/

├── api/

│   └── app/

│       └── routers/

├── dashboard/

├── docs/

├── grafana/

├── influx/

├── mosquitto/

├── nodered/

├── report/

├── simulators/

│   └── air/

├── .env.example

├── .gitignore

├── DISCLOSURE.md

├── docker-compose.yml

└── README.md

```



\## 5. Perangkat Simulator Air



Perangkat yang disimulasikan:



| Device ID | Domain |

|---|---|

| aq-01 | Air Quality |

| aq-02 | Air Quality |

| aq-03 | Air Quality |



Metrik yang dikirim:

\- `co2\_ppm`

\- `pm25\_ugm3`

\- `noise\_db`



Mode simulator:

\- NORMAL

\- CO2\_SPIKE

\- PM\_SPIKE

\- NOISE\_SPIKE

\- STOP

\- CRASH



\## 6. Port Layanan



| Layanan | Port |

|---|---:|

| Mosquitto MQTT | 1883 |

| Node-RED | 1880 |

| InfluxDB | 8086 |

| PostgreSQL | 5432 |

| FastAPI | 8000 |

| Dashboard | 8080 |

| Grafana | 3000 |



\## 7. Cara Menjalankan Proyek



Prasyarat:

\- Docker Desktop

\- Git



Langkah menjalankan (setelah konfigurasi selesai):



1\. Clone repository.

2\. Salin `.env.example` menjadi `.env`.

3\. Isi konfigurasi lingkungan.

4\. Jalankan:



```bash

docker compose up --build -d

```



5\. Buka layanan melalui port yang telah ditentukan.



Catatan: Konfigurasi layanan dan instruksi menjalankan proyek akan diperbarui setelah proses integrasi selesai.



\## 8. Pembagian Tugas Tim



| Anggota | Tanggung Jawab |

|---|---|

| Anggota 1 | Simulator dan aturan domain Air |

| Anggota 2 | API dan tampilan domain Air |

| Anggota 3 | Koordinator integrasi dan dashboard pusat |



Nama anggota dan pembagian tugas akhir akan diperbarui sesuai kesepakatan tim.