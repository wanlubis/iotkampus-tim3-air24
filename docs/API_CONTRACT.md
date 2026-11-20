\# API Integration Contract

\## IoT Kampus AIR24



Dokumen ini menetapkan standar API untuk mengakses data dari seluruh domain IoT Kampus AIR24.



\## 1. Base URL



FastAPI berjalan pada:



`http://localhost:8000`



Dokumentasi API:



`http://localhost:8000/docs`



\## 2. API Authentication



Endpoint yang membutuhkan autentikasi menggunakan API Key melalui HTTP Header:



`X-API-Key: YOUR\_API\_KEY`



API Key diambil dari environment variable `API\_KEY`.



API Key tidak boleh ditulis langsung di source code atau dibagikan melalui repository publik.



\## 3. Health Check



Endpoint:



`GET /health`



Digunakan untuk memeriksa apakah layanan API berjalan.



Contoh response:



```json

{

&#x20; "status": "ok",

&#x20; "service": "iot-kampus-air24"

}

```



\## 4. API Domain



Setiap domain memiliki prefix endpoint masing-masing:



\- Energy: `/api/v1/energy`

\- Cold Chain: `/api/v1/coldchain`

\- Air Quality: `/api/v1/air`



Endpoint domain yang disediakan:



\### Energy — Team 1



Rancangan endpoint:



\- `GET /api/v1/energy/devices`

\- `GET /api/v1/energy/summary`

\- `GET /api/v1/energy/devices/{device\_id}`



Detail response dan metrics akan disepakati bersama Team 1.



\### Cold Chain — Team 2



Rancangan endpoint:



\- `GET /api/v1/coldchain/devices`

\- `GET /api/v1/coldchain/summary`

\- `GET /api/v1/coldchain/devices/{device\_id}`



Detail response dan metrics akan disepakati bersama Team 2.



\### Air Quality — Team 3



Endpoint:



\- `GET /api/v1/air/rooms`

\- `GET /api/v1/air/rooms/{ruang}`



Metrics:

\- `co2\_ppm`

\- `pm25\_ugm3`

\- `noise\_db`



\## 5. Central Summary



Endpoint:



`GET /api/v1/summary`



Digunakan untuk menampilkan ringkasan seluruh domain pada dashboard pusat.



Contoh struktur response:



```json

{

&#x20; "energy": {

&#x20;   "total\_devices": 0,

&#x20;   "status": "initializing"

&#x20; },

&#x20; "coldchain": {

&#x20;   "total\_devices": 0,

&#x20;   "status": "initializing"

&#x20; },

&#x20; "air": {

&#x20;   "total\_rooms": 0,

&#x20;   "status

