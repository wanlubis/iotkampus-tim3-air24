# AI Usage Disclosure — Tim 1 (Smart Energy)

Dokumen ini mencatat penggunaan alat bantu AI selama pengembangan domain **Smart Energy (Tim 1 — AIR24)** pada proyek *Mini IoT Platform Kampus*.

---

## Tim 1 (Smart Energy — Anggota 2: Aldy Alfaisal Pasaribu / `Aldy-create`)

### AI Tool Used
- Antigravity (AI Coding Assistant)

### Purpose of Use
AI assistance was used in a limited supporting role during the development of the Team 1 Smart Energy backend API, unit tests, Grafana panels, and BMS dashboard tab (`#content-energy`):
- Cross-checking alignment with the course specification (`Final Project IoT AIR24.pdf`) and shared API/MQTT contracts.
- Generating initial unit test boilerplate (`api/tests/test_energy_api.py`) and documentation drafts.
- Providing debugging and layout-refactoring suggestions for the FastAPI router, Flux queries, and 2D SVG BMS dashboard (`dashboard/index.html`, `dashboard/energy/`).

### Human Review and Responsibility
The author designed the Smart Energy backend/dashboard architecture, implemented and adjusted the system logic, and verified all features via automated tests (`pytest`) and live Docker end-to-end checks before committing to `team-1-energy`. The author holds full ownership and responsibility for the implementation.

---

## Tim 1 (Smart Energy — Anggota 1: Vincent Junio Ibrahim / `VozzyJun`)

### AI Tool Used
- Antigravity (AI Coding Assistant)

### Purpose of Use
AI assistance was used in a limited supporting role during the development of the Team 1 Smart Energy 4-meter simulator, fault injector, and Node-RED rule engine:
- Cross-checking MQTT topics (`kampus/energy/bsd-a/{ruang}/{device_id}/{channel}`), payload envelopes (`kampus.telemetry.v1`, `kampus.status.v1`), and thresholds against `docs/MQTT_CONTRACT.md` and `api/app/routers/energy.py`.
- Drafting initial boilerplate for the simulator/CLI injector (`simulators/energy/`) and unit test cases (`test_simulator.py`, `nodered/tests/test_rules.js`).
- Assisting with troubleshooting Node-RED rule logic (`Rules - Smart Energy` in `nodered/data/flows.json`).

### Human Review and Responsibility
The author designed, implemented, and validated the simulator, fault injection modes, and Node-RED rule flows via automated Python and Node.js tests before pushing to `team-1-energy`. The author holds full ownership and responsibility for the implementation.
