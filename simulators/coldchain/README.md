# Simulator Cold-Chain / Smart Storage (Tim 2)

Folder ini disediakan untuk kode simulator **3 chamber** (`cc-01` s.d. `cc-03`) milik **Tim 2**.

### Kewajiban Tim 2 (Bagian 6.2 & 6.6):
- Menerbitkan telemetri ke topic: `kampus/coldchain/bsd-a/{ruang}/{device_id}/telemetry`
- Field wajib di `metrics`: `temp_c`, `humidity_pct`, `door_open` (boolean), `battery_pct`, `rssi_dbm`.
- Status LWT/Birth ke: `kampus/coldchain/bsd-a/{ruang}/{device_id}/status`
- Mode pengujian: NORMAL, SPIKE (suhu menembus ambang), DOOR (pintu terbuka terus), STOP, dan CRASH.
