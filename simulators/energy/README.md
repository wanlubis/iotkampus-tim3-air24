# Simulator Smart Energy (Tim 1)

Folder ini disediakan untuk kode simulator **4 kWh meter** (`kwh-01` s.d. `kwh-04`) milik **Tim 1**.

### Kewajiban Tim 1 (Bagian 5.2 & 5.6):
- Menerbitkan telemetri ke topic: `kampus/energy/bsd-a/{ruang}/{device_id}/telemetry`
- Field wajib di `metrics`: `power_w` (W) dan `energy_kwh` (kWh kumulatif non-menurun).
- Status LWT/Birth ke: `kampus/energy/bsd-a/{ruang}/{device_id}/status`
- Mode pengujian: NORMAL, BOROS (beban tinggi di luar jam kerja), LONJAKAN, dan STOP/CRASH.
