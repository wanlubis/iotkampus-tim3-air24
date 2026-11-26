"use strict";

// =========================================
// COLDCHAIN DASHBOARD - TIM 2
// =========================================

const CONFIG = Object.freeze({
    apiBase: "/api/v1",
    refreshMs: 5000,
    timeoutMs: 10000,
    staleMs: 60000,
    warningTemp: 6,
    criticalTemp: 8,
    devices: ["cc-01", "cc-02", "cc-03"],
    colors: {
        "cc-01": "#38bdf8",
        "cc-02": "#4ade80",
        "cc-03": "#c084fc"
    }
});

const state = {
    apiKey: "",
    connected: false,
    connecting: false,
    refreshing: false,
    refreshQueued: false,
    dataStale: true,
    generation: 0,
    timer: null,
    notificationTimer: null,
    chambers: [],
    history: [],
    chartRange: null,
    pendingSetpoints: new Map(),
    pendingAcks: new Set(),
    requestControllers: new Set()
};

const $ = id => document.getElementById(id);

const wibFormatter = new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Jakarta",
    dateStyle: "short",
    timeStyle: "medium"
});

const timeFormatter = new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Jakarta",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
});

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function number(value, decimals = 1, unit = "") {
    return typeof value === "number" && Number.isFinite(value)
        ? `${value.toFixed(decimals)}${unit}`
        : "--";
}

function formatTime(value) {
    if (!value) return "--";

    const date = new Date(value);

    return Number.isFinite(date.getTime())
        ? `${wibFormatter.format(date)} WIB`
        : "--";
}

function formatDuration(seconds) {
    if (typeof seconds !== "number" || !Number.isFinite(seconds)) {
        return "--";
    }

    if (seconds <= 60) return `${seconds} detik`;

    const minutes = Math.floor(seconds / 60);
    const remaining = Math.floor(seconds % 60);

    return `${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
}

function setText(id, value) {
    $(id).textContent = value;
}

function statusClass(value) {
    const allowed = [
        "online", "offline", "active", "acknowledged",
        "resolved", "warning", "critical", "escalated",
        "info", "normal", "stale", "unknown"
    ];

    return allowed.includes(value) ? value : "unknown";
}

function badge(value, type = "status") {
    return `<span class="${type}-badge ${statusClass(value)}">
        ${escapeHtml(value || "unknown")}
    </span>`;
}

function temperatureClass(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
        return "unknown";
    }

    if (value > CONFIG.criticalTemp) return "critical";
    if (value > CONFIG.warningTemp) return "warning";

    return "normal";
}

function isFresh(chamber) {
    const timestamp = Date.parse(chamber.telemetry?.timestamp);

    return Number.isFinite(timestamp) &&
        Date.now() - timestamp < CONFIG.staleMs &&
        timestamp <= Date.now() + 10000;
}

// =========================================
// API CLIENT
// =========================================

async function apiRequest(path, options = {}) {
    const controller = new AbortController();
    state.requestControllers.add(controller);

    const timeout = setTimeout(
        () => controller.abort(),
        CONFIG.timeoutMs
    );

    try {
        const response = await fetch(`${CONFIG.apiBase}${path}`, {
            method: options.method || "GET",
            headers: {
                "X-API-Key": state.apiKey,
                "Content-Type": "application/json"
            },
            body: options.body === undefined
                ? undefined
                : JSON.stringify(options.body),
            signal: controller.signal,
            cache: "no-store"
        });

        if (!response.ok) {
            const messages = {
                401: "API key tidak valid.",
                404: "Data tidak ditemukan.",
                409: "Perangkat offline atau terjadi konflik.",
                422: "Input tidak valid.",
                500: "Terjadi kesalahan pada backend.",
                503: "Layanan sementara tidak tersedia."
            };

            const error = new Error(
                messages[response.status] || `HTTP ${response.status}`
            );

            error.status = response.status;
            throw error;
        }

        return await response.json();

    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error("API request timeout.");
        }

        throw error;

    } finally {
        clearTimeout(timeout);
        state.requestControllers.delete(controller);
    }
}

function readData(response) {
    if (!response || !Array.isArray(response.data)) {
        throw new Error("Format respons API tidak valid.");
    }

    return response.data;
}

// =========================================
// CONNECTION AND NOTIFICATION
// =========================================

function connectionStatus(text, cssClass) {
    const element = $("connection-status");

    element.textContent = text;
    element.className = `status-badge ${cssClass}`;
}

function notify(message, type = "success") {
    const element = $("notification");

    clearTimeout(state.notificationTimer);

    element.textContent = message;
    element.className = type;
    element.hidden = false;

    state.notificationTimer = setTimeout(() => {
        element.hidden = true;
    }, 6000);
}

function showError(message) {
    $("error-banner").textContent = message;
    $("error-banner").hidden = false;
}

function clearError() {
    $("error-banner").hidden = true;
    $("error-banner").textContent = "";
}

async function connect(event) {
    event.preventDefault();

    if (state.connected || state.connecting) return;

    const key = $("api-key").value.trim();

    if (!key) return;

    const button = $("auth-form").querySelector("button");

    state.connecting = true;
    button.disabled = true;
    state.apiKey = key;

    setText("auth-message", "Menghubungkan ke backend...");

    try {
        const response = await apiRequest("/coldchain/chambers");

        readData(response);

        state.generation++;
        state.connected = true;

        $("api-key").value = "";
        $("auth-panel").hidden = true;
        $("dashboard-content").hidden = false;
        $("disconnect-button").hidden = false;

        connectionStatus("Connected", "connected");
        setText("auth-message", "");

        await refreshDashboard();

        if (state.connected) {
            startAutoRefresh();
        }

    } catch (error) {
        state.apiKey = "";
        state.connected = false;

        connectionStatus("Disconnected", "disconnected");
        setText("auth-message", error.message);

    } finally {
        state.connecting = false;
        button.disabled = false;
    }
}

function disconnect(message = "") {
    clearTimeout(state.timer);
    clearTimeout(state.notificationTimer);

    state.generation++;

    for (const controller of state.requestControllers) {
        controller.abort();
    }
    state.requestControllers.clear();

    state.connected = false;
    state.refreshing = false;
    state.refreshQueued = false;
    state.dataStale = true;
    state.apiKey = "";
    state.chambers = [];
    state.history = [];
    state.chartRange = null;

    for (const pending of state.pendingSetpoints.values()) {
        clearTimeout(pending.timer);
    }
    state.pendingSetpoints.clear();
    state.pendingAcks.clear();

    $("api-key").value = "";
    $("dashboard-content").hidden = true;
    $("refresh-button").disabled = false;
    $("disconnect-button").hidden = true;
    $("auth-panel").hidden = false;
    $("notification").hidden = true;
    $("chamber-grid").replaceChildren();
    $("alert-table-body").replaceChildren();
    $("escalation-table-body").replaceChildren();

    connectionStatus("Disconnected", "disconnected");

    setText("auth-message", message);

    clearError();
}

function startAutoRefresh() {
    clearTimeout(state.timer);

    if (!state.connected) return;

    const generation = state.generation;

    state.timer = setTimeout(async () => {
        if (generation !== state.generation) return;

        await refreshDashboard();

        if (generation === state.generation) {
            startAutoRefresh();
        }
    }, CONFIG.refreshMs);
}

// =========================================
// KPI MONITORING
// =========================================

function renderKpis(chambers, activeAlerts, acknowledgedAlerts) {
    const total = chambers.length;

    const online = chambers.filter(
        chamber => chamber.status === "online"
    ).length;

    const fresh = chambers.filter(
        chamber => chamber.status === "online" && isFresh(chamber)
    );

    const temperatures = fresh
        .map(chamber => chamber.telemetry?.temp_c)
        .filter(value => typeof value === "number" &&
            Number.isFinite(value));

    const average = temperatures.length
        ? temperatures.reduce((sum, value) => sum + value, 0)
            / temperatures.length
        : null;

    const knownDoors = fresh.filter(
        chamber => typeof chamber.telemetry?.door_open === "boolean"
    );

    const openDoors = knownDoors.filter(
        chamber => chamber.telemetry.door_open === true
    ).length;

    setText("kpi-online", `${online}/${total}`);
    setText("kpi-online-detail", `${total - online} tidak online`);

    setText("kpi-temperature", number(average, 2, " °C"));

    setText("kpi-alerts", activeAlerts.length);
    setText(
        "kpi-alert-detail",
        `${acknowledgedAlerts.length} acknowledged`
    );

    setText(
        "kpi-doors",
        knownDoors.length ? `${openDoors}/${knownDoors.length}` : "--"
    );

    setText(
        "kpi-door-detail",
        `${total - knownDoors.length} status pintu tidak terkini`
    );

    $("kpi-temperature").className = temperatureClass(average);
    $("kpi-alerts").className = activeAlerts.length ? "critical" : "normal";
    $("kpi-doors").className = !knownDoors.length
        ? "unknown"
        : openDoors ? "warning" : "normal";
}

// =========================================
// CHAMBER MONITORING
// =========================================

function clearPendingSetpoint(deviceId) {
    const pending = state.pendingSetpoints.get(deviceId);
    if (!pending) return;
    clearTimeout(pending.timer);
    state.pendingSetpoints.delete(deviceId);
}

function checkSetpointConfirmation(chambers) {
    for (const [deviceId, pending] of state.pendingSetpoints) {
        if (pending.sending) continue;

        const chamber = chambers.find(
            item => item.device_id === deviceId
        );

        const telemetry = chamber?.telemetry;
        const timestamp = Date.parse(telemetry?.timestamp);

        if (
            chamber?.status === "online" &&
            isFresh(chamber) &&
            timestamp > pending.previousTimestamp &&
            timestamp >= pending.requestedAt &&
            typeof telemetry?.setpoint_c === "number" &&
            Math.abs(telemetry.setpoint_c - pending.value) < 0.001
        ) {
            clearPendingSetpoint(deviceId);

            notify(
                `${deviceId}: setpoint ${pending.value} °C terkonfirmasi melalui telemetry.`
            );

        } else if (Date.now() > pending.deadline) {
            clearPendingSetpoint(deviceId);

            notify(
                `${deviceId}: setpoint belum terkonfirmasi melalui telemetry.`,
                "warning"
            );
        }
    }
}

function renderChambers(chambers) {
    const container = $("chamber-grid");
    const drafts = new Map();

    container.querySelectorAll(".setpoint-form").forEach(form => {
        const input = form.querySelector("input");

        if (
            input &&
            !input.disabled &&
            input.value !== input.defaultValue
        ) {
            drafts.set(form.dataset.device, input.value);
        }
    });

    const focusedInput = document.activeElement;
    const focusedDevice = focusedInput?.matches(
        ".setpoint-form input"
    ) ? focusedInput.closest(".setpoint-form")?.dataset.device
        : null;

    if (!chambers.length) {
        container.innerHTML = "<p>Tidak ada chamber.</p>";
        return;
    }

    container.innerHTML = chambers.map(chamber => {
        const id = chamber.device_id;
        const telemetry = chamber.telemetry || {};

        const online = chamber.status === "online";
        const fresh = online && isFresh(chamber);
        const pending = state.pendingSetpoints.get(id);

        const doorText = !fresh ||
            typeof telemetry.door_open !== "boolean"
            ? "Unknown"
            : telemetry.door_open ? "Open" : "Closed";

        const doorClass = doorText.toLowerCase();

        const dataStatus = fresh
            ? "Telemetry current"
            : "Telemetry stale / unavailable";

        const currentSetpoint =
            typeof telemetry.setpoint_c === "number"
                ? telemetry.setpoint_c
                : "";

        return `
            <article class="chamber-card">
                <div class="chamber-header">
                    <div>
                        <h3>${escapeHtml(id)}</h3>
                        <p class="chamber-location">
                            ${escapeHtml(chamber.gedung)} /
                            ${escapeHtml(chamber.ruang)}
                        </p>
                    </div>
                    ${badge(chamber.status)}
                </div>

                <div class="chamber-temperature ${
                    fresh ? temperatureClass(telemetry.temp_c) : "unknown"
                }">
                    ${number(telemetry.temp_c, 2, " °C")}
                </div>

                <p class="${fresh ? "normal" : "stale"}">
                    ${dataStatus}
                </p>

                <div class="metric-grid">
                    <div class="metric">
                        <span class="metric-label">Humidity</span>
                        <span class="metric-value">
                            ${number(telemetry.humidity_pct, 2, "%")}
                        </span>
                    </div>

                    <div class="metric">
                        <span class="metric-label">Door</span>
                        <span class="metric-value ${doorClass}">
                            ${doorText}
                        </span>
                    </div>

                    <div class="metric">
                        <span class="metric-label">Battery</span>
                        <span class="metric-value">
                            ${number(telemetry.battery_pct, 0, "%")}
                        </span>
                    </div>

                    <div class="metric">
                        <span class="metric-label">RSSI</span>
                        <span class="metric-value">
                            ${number(telemetry.rssi_dbm, 0, " dBm")}
                        </span>
                    </div>
                </div>

                <div class="chamber-footer">
                    <p>Current setpoint:
                        <strong>
                            ${number(telemetry.setpoint_c, 1, " °C")}
                        </strong>
                    </p>

                    <form class="setpoint-form"
                          data-device="${escapeHtml(id)}">

                        <label for="setpoint-${escapeHtml(id)}">
                            New setpoint (0 - 10 °C)
                        </label>

                        <input
                            id="setpoint-${escapeHtml(id)}"
                            type="number"
                            min="0"
                            max="10"
                            step="0.1"
                            value="${escapeHtml(currentSetpoint)}"
                            required
                            ${state.dataStale || !fresh || pending ? "disabled" : ""}
                        >

                        <button
                            type="submit"
                            class="setpoint-button"
                            ${state.dataStale || !fresh || pending ? "disabled" : ""}
                        >
                            Apply
                        </button>
                    </form>

                    <p class="setpoint-message">
                        ${pending
                            ? `Menunggu konfirmasi ${pending.value} °C`
                            : ""}
                    </p>

                    <small>Last seen:
                        ${escapeHtml(formatTime(chamber.last_seen))}
                    </small>

                    <small>Telemetry:
                        ${escapeHtml(formatTime(telemetry.timestamp))}
                    </small>
                </div>
            </article>
        `;
    }).join("");

    container.querySelectorAll(".setpoint-form").forEach(form => {
        const id = form.dataset.device;
        const input = form.querySelector("input");
        const pending = state.pendingSetpoints.get(id);

        if (!input) return;

        if (pending) {
            input.value = String(pending.value);
        } else if (drafts.has(id)) {
            input.value = drafts.get(id);
        }
    });

    if (focusedDevice) {
        const input = document.getElementById(
            `setpoint-${focusedDevice}`
        );

        if (input && !input.disabled) {
            input.focus({ preventScroll: true });
        }
    }
}

// =========================================
// SETPOINT COMMAND
// =========================================

async function submitSetpoint(event) {
    const form = event.target.closest(".setpoint-form");

    if (!form) return;

    event.preventDefault();

    const id = form.dataset.device;
    const input = form.querySelector("input");
    const value = input.valueAsNumber;

    const chamber = state.chambers.find(
        item => item.device_id === id
    );

    if (
        !state.connected ||
        state.dataStale ||
        !chamber ||
        chamber.status !== "online" ||
        !isFresh(chamber) ||
        state.pendingSetpoints.has(id)
    ) {
        notify("Perangkat belum siap menerima command.", "warning");
        return;
    }

    if (!Number.isFinite(value) || value < 0 || value > 10) {
        notify("Setpoint harus antara 0 dan 10 °C.", "error");
        return;
    }

    if (
        typeof chamber.telemetry?.setpoint_c === "number" &&
        Math.abs(chamber.telemetry.setpoint_c - value) < 0.001
    ) {
        notify(
            `${id}: setpoint sudah sesuai dengan nilai yang diminta.`,
            "warning"
        );
        return;
    }

    if (!window.confirm(`Ubah setpoint ${id} menjadi ${value} °C?`)) {
        return;
    }

    const generation = state.generation;

    const pending = {
        value,
        sending: true,
        previousTimestamp: Date.parse(chamber.telemetry.timestamp),
        requestedAt: Date.now(),
        timer: null,
        deadline: Date.now() + 30000
    };

    state.pendingSetpoints.set(id, pending);

    renderChambers(state.chambers);

    try {
        await apiRequest(
            `/coldchain/cmd/${encodeURIComponent(id)}`,
            {
                method: "POST",
                body: {
                    command: "setpoint",
                    args: { temp_c: value }
                }
            }
        );

        if (generation !== state.generation) return;

        pending.sending = false;
        pending.deadline = Date.now() + 30000;
        pending.timer = setTimeout(() => {
            if (generation !== state.generation ||
                !state.connected ||
                state.pendingSetpoints.get(id) !== pending) return;

            clearPendingSetpoint(id);
            notify(
                `${id}: setpoint belum terkonfirmasi melalui telemetry.`,
                "warning"
            );

            renderChambers(state.chambers);
        }, 30000);

        notify(
            `${id}: command dipublikasikan. Menunggu telemetry.`,
            "warning"
        );

    } catch (error) {
        if (generation !== state.generation) return;

        clearPendingSetpoint(id);

        if (error.status === 401) {
            disconnect(error.message);
            return;
        }

        notify(error.message, "error");

    } finally {
        if (generation === state.generation && state.connected) {
            renderChambers(state.chambers);
        }
    }
}

// =========================================
// ALERT MONITORING
// =========================================

function renderAlerts(alerts) {
    const body = $("alert-table-body");

    if (!alerts.length) {
        body.innerHTML = `
            <tr><td colspan="7">Tidak ada alert.</td></tr>
        `;
        return;
    }

    body.innerHTML = alerts.map(alert => {
        const canAck = alert.status === "active" &&
            Number.isSafeInteger(alert.alert_id);

        const pending = state.pendingAcks.has(alert.alert_id);

        return `
            <tr>
                <td class="alert-id">#${escapeHtml(alert.alert_id)}</td>
                <td>${escapeHtml(alert.device_id)}</td>
                <td title="${escapeHtml(alert.message)}">
                    ${escapeHtml(alert.alert_type)}
                </td>
                <td>${badge(alert.severity, "severity")}</td>
                <td>${badge(alert.status)}</td>
                <td>${escapeHtml(formatTime(alert.triggered_at))}</td>
                <td>
                    ${canAck
                        ? `<button
                            type="button"
                            class="ack-button"
                            data-alert-id="${alert.alert_id}"
                            ${state.dataStale || pending ? "disabled" : ""}
                           >ACK</button>`
                        : escapeHtml(alert.acknowledged_by || "--")}
                </td>
            </tr>
        `;
    }).join("");
}

async function acknowledgeAlert(event) {
    const button = event.target.closest(".ack-button");

    if (!button || !state.connected || state.dataStale) return;

    const id = Number(button.dataset.alertId);

    if (!Number.isSafeInteger(id) || state.pendingAcks.has(id)) {
        return;
    }

    const operator = window.prompt(
        "Masukkan nama operator:",
        "operator"
    );

    if (operator === null) return;

    const name = operator.trim();

    if (!name || name.length > 100) {
        notify("Nama operator harus 1-100 karakter.", "error");
        return;
    }

    const generation = state.generation;

    state.pendingAcks.add(id);
    button.disabled = true;

    try {
        await apiRequest(`/alerts/${id}/ack`, {
            method: "POST",
            body: { acked_by: name }
        });

        if (generation !== state.generation) return;

        notify(`Alert #${id} berhasil di-acknowledge.`);

        await refreshDashboard();

    } catch (error) {
        if (generation !== state.generation) return;

        if (error.status === 401) {
            disconnect(error.message);
            return;
        }

        notify(error.message, "error");

    } finally {
        if (generation === state.generation) {
            state.pendingAcks.delete(id);
            button.disabled = state.dataStale;
        }
    }
}

// =========================================
// ESCALATION MONITORING
// =========================================

function renderEscalations(alerts) {
    const body = $("escalation-table-body");

    if (!alerts.length) {
        body.innerHTML = `
            <tr><td colspan="7">Tidak ada escalation.</td></tr>
        `;
        return;
    }

    const sorted = [...alerts].sort(
        (a, b) => Date.parse(b.triggered_at) -
            Date.parse(a.triggered_at) ||
            b.alert_id - a.alert_id
    );

    body.innerHTML = sorted.slice(0, 50).map(alert => {
        const metadata = alert.metadata || {};

        return `
            <tr>
                <td>${escapeHtml(alert.device_id)}</td>
                <td>
                    ${escapeHtml(metadata.original_alert_type || "--")}
                    #${escapeHtml(metadata.original_alert_id ?? "--")}
                </td>
                <td class="escalated">
                    #${escapeHtml(alert.alert_id)}
                    ${escapeHtml(alert.alert_type)}
                </td>
                <td>${number(metadata.temp_c, 2, " °C")}</td>
                <td>${formatDuration(metadata.duration_seconds)}</td>
                <td>${badge(alert.status)}</td>
                <td>${escapeHtml(formatTime(alert.triggered_at))}</td>
            </tr>
        `;
    }).join("");
}

// =========================================
// TELEMETRY HISTORY
// =========================================

async function loadHistory() {
    const selected = $("device-filter").value;
    const minutes = Number($("time-range").value);

    const devices = selected === "all"
        ? CONFIG.devices
        : CONFIG.devices.filter(id => id === selected);

    const end = Date.now();
    const start = end - minutes * 60000;

    const responses = await Promise.all(devices.map(id => {
        const params = new URLSearchParams({
            domain: "coldchain",
            device_id: id,
            from: new Date(start).toISOString(),
            to: new Date(end).toISOString(),
            limit: "1000"
        });

        return apiRequest(`/telemetry?${params}`);
    }));

    const records = responses.flatMap(readData);

    return {
        records,
        start,
        end,
        devices,
        selected,
        minutes
    };
}

// =========================================
// NATIVE CANVAS CHARTS
// =========================================

function drawChart(canvasId, emptyId, metric, temperature) {
    const canvas = $(canvasId);
    const range = state.chartRange;

    if (!range) return;

    const series = range.devices.map(id => ({
        id,
        color: CONFIG.colors[id],
        points: state.history
            .filter(record => record.device_id === id)
            .map(record => ({
                time: Date.parse(record.timestamp),
                value: record.metrics?.[metric]
            }))
            .filter(point =>
                Number.isFinite(point.time) &&
                typeof point.value === "number" &&
                Number.isFinite(point.value) &&
                point.time >= range.start &&
                point.time <= range.end
            )
            .sort((a, b) => a.time - b.time)
    }));

    const values = series.flatMap(
        item => item.points.map(point => point.value)
    );

    const rect = canvas.getBoundingClientRect();

    if (!rect.width || !rect.height) return;

    const ratio = window.devicePixelRatio || 1;

    canvas.width = Math.round(rect.width * ratio);
    canvas.height = Math.round(rect.height * ratio);

    const ctx = canvas.getContext("2d");

    ctx.scale(ratio, ratio);

    const width = rect.width;
    const height = rect.height;

    ctx.clearRect(0, 0, width, height);

    $(emptyId).hidden = values.length > 0;

    if (!values.length) return;

    const min = temperature
        ? Math.min(0, Math.floor(Math.min(...values)))
        : Math.min(0, Math.floor(Math.min(...values)));

    const max = temperature
        ? Math.max(10, Math.ceil(Math.max(...values)))
        : Math.max(100, Math.ceil(Math.max(...values)));

    const left = 48;
    const right = width - 16;
    const top = 30;
    const bottom = height - 32;

    if (right <= left || bottom <= top) return;

    const x = time => left +
        (time - range.start) /
        (range.end - range.start) * (right - left);

    const y = value => bottom -
        (value - min) / (max - min) * (bottom - top);

    ctx.font = "11px Segoe UI, Arial";
    ctx.lineWidth = 1;

    for (let i = 0; i <= 5; i++) {
        const value = min + (max - min) * i / 5;
        const position = y(value);

        ctx.strokeStyle = "#334155";
        ctx.beginPath();
        ctx.moveTo(left, position);
        ctx.lineTo(right, position);
        ctx.stroke();

        ctx.fillStyle = "#94a3b8";
        ctx.textAlign = "right";
        ctx.fillText(value.toFixed(1), left - 7, position + 4);
    }

    for (let i = 0; i <= 4; i++) {
        const timestamp = range.start +
            (range.end - range.start) * i / 4;

        const position = x(timestamp);

        ctx.fillStyle = "#94a3b8";
        ctx.textAlign = i === 0 ? "left" :
            i === 4 ? "right" : "center";

        ctx.fillText(
            timeFormatter.format(new Date(timestamp)),
            position,
            bottom + 20
        );
    }

    if (temperature) {
        [
            [CONFIG.warningTemp, "#fbbf24"],
            [CONFIG.criticalTemp, "#ef4444"]
        ].forEach(([threshold, color]) => {
            ctx.strokeStyle = color;
            ctx.setLineDash([6, 4]);

            ctx.beginPath();
            ctx.moveTo(left, y(threshold));
            ctx.lineTo(right, y(threshold));
            ctx.stroke();

            ctx.setLineDash([]);
        });
    }

    ctx.save();

    ctx.beginPath();
    ctx.rect(left, top, right - left, bottom - top);
    ctx.clip();

    series.forEach(item => {
        ctx.strokeStyle = item.color;
        ctx.fillStyle = item.color;
        ctx.lineWidth = 2;
        ctx.beginPath();

        let previous = null;

        item.points.forEach(point => {
            if (!previous || point.time - previous.time > 15000) {
                ctx.moveTo(x(point.time), y(point.value));
            } else {
                ctx.lineTo(x(point.time), y(point.value));
            }

            previous = point;
        });

        ctx.stroke();

        item.points.forEach(point => {
            ctx.beginPath();
            ctx.arc(x(point.time), y(point.value), 1.5, 0, Math.PI * 2);
            ctx.fill();
        });
    });

    ctx.restore();

    ctx.textAlign = "left";

    series.forEach((item, index) => {
        const position = left + index * 72;

        ctx.fillStyle = item.color;
        ctx.fillRect(position, 8, 10, 3);
        ctx.fillText(item.id, position + 15, 14);
    });
}

function renderCharts() {
    drawChart(
        "temperature-chart",
        "temperature-empty",
        "temp_c",
        true
    );

    drawChart(
        "humidity-chart",
        "humidity-empty",
        "humidity_pct",
        false
    );
}

// =========================================
// DASHBOARD REFRESH
// =========================================

async function refreshDashboard() {
    if (!state.connected) return;

    if (state.refreshing) {
        state.refreshQueued = true;
        return;
    }

    state.refreshQueued = false;

    const generation = state.generation;

    state.refreshing = true;
    $("refresh-button").disabled = true;

    try {
        const alertStatus = $("alert-filter").value;

        const alertParams = new URLSearchParams({
            domain: "coldchain",
            limit: "50"
        });

        if (alertStatus !== "all") {
            alertParams.set("status", alertStatus);
        }

        const [
            chambersResponse,
            activeResponse,
            acknowledgedResponse,
            alertsResponse,
            escalationResponse,
            history
        ] = await Promise.all([
            apiRequest("/coldchain/chambers"),

            apiRequest(
                "/alerts?domain=coldchain&status=active&limit=1000"
            ),

            apiRequest(
                "/alerts?domain=coldchain&status=acknowledged&limit=1000"
            ),

            apiRequest(`/alerts?${alertParams}`),

            apiRequest("/coldchain/escalations"),

            loadHistory()
        ]);

        if (
            generation !== state.generation ||
            !state.connected
        ) return;

        const chambers = readData(chambersResponse);
        const active = readData(activeResponse);
        const acknowledged = readData(acknowledgedResponse);
        const alerts = readData(alertsResponse);
        const escalations = readData(escalationResponse);

        state.chambers = chambers;
        state.dataStale = false;

        checkSetpointConfirmation(chambers);

        renderKpis(chambers, active, acknowledged);
        renderChambers(chambers);

        if ($("alert-filter").value === alertStatus) {
            renderAlerts(alerts);
        }

        renderEscalations(escalations);

        if (
            $("device-filter").value === history.selected &&
            Number($("time-range").value) === history.minutes
        ) {
            state.history = history.records;
            state.chartRange = history;

            renderCharts();
        }

        setText("last-update", formatTime(new Date()));

        connectionStatus("Connected", "connected");

        clearError();

        if (active.length >= 1000 || acknowledged.length >= 1000) {
            showError("Jumlah alert mencapai batas API. KPI mungkin tidak lengkap.");
        }

    } catch (error) {
        if (generation !== state.generation) return;

        if (error.status === 401) {
            disconnect(error.message);
            return;
        }

        state.dataStale = true;
        connectionStatus("Data stale", "stale");

        showError(
            `${error.message} Data terakhir mungkin sudah tidak terkini.`
        );

        document.querySelectorAll(
            ".setpoint-form input, .setpoint-button, .ack-button"
        ).forEach(element => {
            element.disabled = true;
        });

    } finally {
        if (generation === state.generation) {
            state.refreshing = false;
            $("refresh-button").disabled = false;

            if (state.connected && state.refreshQueued) {
                state.refreshQueued = false;
                void refreshDashboard();
            }
        }
    }
}

// =========================================
// INITIALIZATION
// =========================================

function initialize() {
    $("auth-form").addEventListener("submit", connect);

    $("disconnect-button").addEventListener(
        "click",
        () => disconnect()
    );

    $("refresh-button").addEventListener(
        "click",
        refreshDashboard
    );

    $("chamber-grid").addEventListener(
        "submit",
        submitSetpoint
    );

    $("alert-table-body").addEventListener(
        "click",
        acknowledgeAlert
    );

    ["device-filter", "time-range", "alert-filter"].forEach(id => {
        $(id).addEventListener("change", refreshDashboard);
    });

    window.addEventListener("resize", () => {
        if (state.connected) renderCharts();
    });

    connectionStatus("Disconnected", "disconnected");
}

document.addEventListener("DOMContentLoaded", initialize);