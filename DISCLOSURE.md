# AI Usage Disclosure

## 1. Informasi Proyek

- Mata Kuliah: Final Project IoT — CSEB3073
- Kelas: AIR24
- Tim: Team 2
- Domain: Cold-Chain / Smart Storage
- Proyek: Cold-Chain IoT Monitoring System

## 2. AI Tool yang Digunakan

OpenAI ChatGPT digunakan sebagai alat bantu dalam proses
pengembangan, debugging, pengujian, dan dokumentasi proyek.

## 3. Lingkup Penggunaan AI

| Komponen | Bentuk Bantuan AI |
|---|---|
| System Architecture | Perencanaan arsitektur dan alur komunikasi |
| Docker Compose | Penyusunan dan perbaikan konfigurasi layanan |
| MQTT | Konfigurasi broker, ACL, autentikasi, dan topic |
| Python Simulator | Penyusunan kode simulator dan skenario pengujian |
| Node-RED | Penyusunan flow, validasi data, dan alert rules |
| InfluxDB | Penyusunan query dan struktur penyimpanan telemetry |
| PostgreSQL | Penyusunan schema, query, dan migration |
| FastAPI | Penyusunan endpoint, autentikasi, dan validasi |
| Transactional Outbox | Perancangan sinkronisasi dan retry mechanism |
| Grafana | Penyusunan query, panel, dan dashboard provisioning |
| HTML/CSS/JavaScript | Penyusunan kode dashboard monitoring dan kontrol |
| Security | Identifikasi risiko dan usulan security hardening |
| Testing | Penyusunan skenario, checklist, dan analisis hasil |
| Debugging | Analisis error dan rekomendasi perbaikan |
| Documentation | Penyusunan README dan dokumentasi teknis |
| Git | Panduan version control, commit, dan push |

AI memberikan bantuan berupa penjelasan, rekomendasi teknis,
contoh kode, kode implementasi, konfigurasi, perintah terminal,
dan rancangan dokumentasi.

## 4. Verifikasi dan Kontribusi Mahasiswa

Mahasiswa menjalankan dan mengonfigurasi sistem pada lingkungan
pengembangan lokal menggunakan Docker Desktop, PowerShell,
Node-RED, Grafana, browser, dan Python.

Proses verifikasi yang dilakukan mencakup:

- Menjalankan perintah instalasi dan konfigurasi.
- Menerapkan dan menyesuaikan kode yang disarankan AI.
- Memeriksa output terminal dan log layanan.
- Menguji komunikasi MQTT.
- Menguji REST API dan autentikasi.
- Memeriksa data pada PostgreSQL dan InfluxDB.
- Menguji simulator pada berbagai kondisi.
- Memverifikasi alert, acknowledgement, escalation, dan recovery.
- Menguji pengiriman dan penerapan setpoint.
- Memeriksa tampilan dan fungsi dashboard.
- Melakukan regression testing setelah perubahan kode.
- Melakukan commit dan push melalui Git.

Hasil pengujian aktual diperoleh dari lingkungan pengembangan
lokal dan digunakan untuk mengevaluasi rekomendasi AI.

## 5. Keterbatasan Penggunaan AI

Kode dan rekomendasi yang dihasilkan AI tidak selalu benar,
lengkap, atau langsung kompatibel dengan konfigurasi proyek.

Selama pengembangan, ditemukan kondisi yang membutuhkan
penyesuaian, debugging, dan pengujian ulang.

Penggunaan AI tidak menggantikan kebutuhan mahasiswa untuk
memahami arsitektur, kode, konfigurasi, dan perilaku sistem.

Hasil pengujian lokal tidak menjamin sistem bebas bug atau
memenuhi seluruh standar keamanan produksi.

## 6. Keamanan dan Privasi

Kredensial sistem dikelola melalui konfigurasi lokal.

File environment, password MQTT, token, dan credential file
tidak dimaksudkan untuk disimpan dalam repository Git.

Informasi autentikasi yang tidak sengaja muncul dalam proses
debugging harus ditangani dengan penghapusan atau rotasi
kredensial yang relevan.

Dokumen ini tidak mencantumkan nilai password, token,
API key, atau informasi autentikasi aktual.

## 7. Tanggung Jawab Akademik

AI digunakan sebagai alat bantu pengembangan dan pembelajaran.

Mahasiswa tetap bertanggung jawab atas:

- Pemahaman terhadap implementasi proyek.
- Validasi kode dan konfigurasi.
- Ketepatan hasil pengujian.
- Keamanan sistem dan pengelolaan kredensial.
- Integrasi dengan tim lain.
- Isi laporan akhir.
- Presentasi dan demonstrasi proyek.

Dokumen ini disusun untuk memberikan transparansi mengenai
penggunaan AI dalam pengerjaan Final Project IoT Team 2.

## 8. Repository

https://github.com/ericsonmeo/coldchain-tim2
