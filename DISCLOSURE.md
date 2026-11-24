AI Usage Disclosure



AI Tool Used

\- ChatGPT



Purpose of Use

ChatGPT was used as an assistant during the development of the Team 3 Smart Environment / Air Quality project.



The assistance included:

\- Understanding the project requirements and system architecture.

\- Planning the project folder structure.

\- Providing step-by-step development guidance.

\- Helping explain code and troubleshoot technical issues.



Human Review and Responsibility

All AI-generated suggestions and code are reviewed, tested, and adjusted by the team before being used in the project.



The team is responsible for understanding, validating, and maintaining the final implementation.

---

## Tim 1 (Smart Energy — Anggota 2: Aldy / `Aldy-create`)

### AI Tool Used
- Antigravity (AI Coding Assistant)

### Purpose of Use
AI assistance was used during the development of the Team 1 Smart Energy backend API, unit tests, Grafana panels, and interactive 3D/2D dashboard tab (`#content-energy`):
- Reviewing compliance against the course specification (`Final Project IoT AIR24.pdf`) and shared API/MQTT contracts.
- Assisting with FastAPI router implementation (`api/app/routers/energy.py`), pytest unit test scaffolding (`api/tests/test_energy_api.py`), and Flux query validation for Grafana (`grafana/provisioning/dashboards/air24_observability.json`).
- Designing and refactoring the Smart Energy dashboard tab (`dashboard/index.html`) including Chart.js analytics and the Three.js 3D Digital Twin HUD.
- Auditing edge cases and verifying syntax/unit tests before committing to branch `team-1-energy`.

### Human Review and Responsibility
All AI-assisted code and documentation were reviewed, verified via automated tests (`pytest`, syntax validation), and tested locally before submission. The author remains fully responsible for understanding and defending the implementation.

---

## Tim 1 (Smart Energy — Anggota 1: Vincent / `VozzyJun`)

### AI Tool Used
- Antigravity (AI Coding Assistant)

### Purpose of Use
AI assistance was used during the development of the Team 1 Smart Energy 4-meter simulator, fault injector, and Node-RED rule engine:
- Aligning MQTT topics (`kampus/energy/bsd-a/{ruang}/{device_id}/{channel}`), payload envelopes (`kampus.telemetry.v1`, `kampus.status.v1`), and thresholds against `docs/MQTT_CONTRACT.md` and `api/app/routers/energy.py`.
- Scaffolding the multi-client Paho MQTT v2 simulator (`simulators/energy/simulator.py`, `devices_config.py`), CLI fault injector (`inject.py`, `inject_event.py`), Dockerfile, and simulator unit tests (`test_simulator.py`).
- Implementing the self-contained `Rules - Smart Energy` tab in `nodered/data/flows.json` (`WASTE_AFTER_HOURS`, `HIGH_LOAD`, `OFFLINE` LWT & 60s watchdog, deduplication, auto-resolve) along with unit tests (`nodered/tests/test_rules.js`).

### Human Review and Responsibility
All AI-assisted code, Node-RED flow additions, and documentation were reviewed, tested via automated Python (`test_simulator.py`) and Node.js (`test_rules.js` + embedded `flows.json` cross-tests), and verified not to overwrite other team members' files before pushing to `team-1-energy`. The author remains fully responsible for understanding and explaining the implementation during individual evaluation.

