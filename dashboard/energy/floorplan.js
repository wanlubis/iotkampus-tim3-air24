// Interactive 2D Architectural Floor Plan (SVG) Component
// Top-down blueprint for Gedung BSD-A Lantai 3 (60 FPS lightweight SVG)

import { FLOORPLAN_ROOMS, STATUS_META } from './constants.js';

function buildDoorSwingSvg(door) {
  const { x, y, w, dir } = door;
  // Clear wall opening mask + thin door leaf + dashed quarter-circle swing arc
  if (dir === 'up-left') {
    return `
      <line x1="${x}" y1="${y}" x2="${x + w}" y2="${y}" stroke="#0b1323" stroke-width="5" />
      <line x1="${x}" y1="${y}" x2="${x}" y2="${y - w}" stroke="#64748b" stroke-width="1.5" />
      <path d="M ${x} ${y - w} A ${w} ${w} 0 0 1 ${x + w} ${y}" fill="none" stroke="#475569" stroke-width="1" stroke-dasharray="3 3" />
    `;
  }
  if (dir === 'up-right') {
    return `
      <line x1="${x}" y1="${y}" x2="${x + w}" y2="${y}" stroke="#0b1323" stroke-width="5" />
      <line x1="${x + w}" y1="${y}" x2="${x + w}" y2="${y - w}" stroke="#64748b" stroke-width="1.5" />
      <path d="M ${x + w} ${y - w} A ${w} ${w} 0 0 0 ${x} ${y}" fill="none" stroke="#475569" stroke-width="1" stroke-dasharray="3 3" />
    `;
  }
  if (dir === 'down-left') {
    return `
      <line x1="${x}" y1="${y}" x2="${x + w}" y2="${y}" stroke="#0b1323" stroke-width="5" />
      <line x1="${x}" y1="${y}" x2="${x}" y2="${y + w}" stroke="#64748b" stroke-width="1.5" />
      <path d="M ${x} ${y + w} A ${w} ${w} 0 0 0 ${x + w} ${y}" fill="none" stroke="#475569" stroke-width="1" stroke-dasharray="3 3" />
    `;
  }
  return `
    <line x1="${x}" y1="${y}" x2="${x + w}" y2="${y}" stroke="#0b1323" stroke-width="5" />
    <line x1="${x + w}" y1="${y}" x2="${x + w}" y2="${y + w}" stroke="#64748b" stroke-width="1.5" />
    <path d="M ${x + w} ${y + w} A ${w} ${w} 0 0 1 ${x} ${y}" fill="none" stroke="#475569" stroke-width="1" stroke-dasharray="3 3" />
  `;
}

function buildInteriorBlueprintDetails(cfg) {
  const { x, y, w, h } = cfg.rect;
  const stroke = 'rgba(148, 163, 184, 0.16)';
  const fill = 'rgba(148, 163, 184, 0.04)';

  if (cfg.type === 'classroom') {
    // Minimalist lecture desks + whiteboard + 2 split AC wall units + 4 ceiling light fixtures
    return `
      <g class="pointer-events-none" stroke="${stroke}" fill="${fill}" stroke-width="1">
        <!-- Whiteboard on west wall -->
        <line x1="${x + 7}" y1="${y + 34}" x2="${x + 7}" y2="${y + 116}" stroke="rgba(148,163,184,0.28)" stroke-width="2" />
        <!-- Split AC units along north wall -->
        <rect x="${x + 56}" y="${y + 4}" width="38" height="9" rx="2" />
        <line x1="${x + 62}" y1="${y + 11}" x2="${x + 88}" y2="${y + 11}" stroke-dasharray="3 2" />
        <rect x="${x + 206}" y="${y + 4}" width="38" height="9" rx="2" />
        <line x1="${x + 212}" y1="${y + 11}" x2="${x + 238}" y2="${y + 11}" stroke-dasharray="3 2" />
        <!-- Minimalist desk blocks -->
        <rect x="${x + 22}" y="${y + 32}" width="36" height="14" rx="2" />
        <rect x="${x + 22}" y="${y + 104}" width="36" height="14" rx="2" />
        <rect x="${x + 242}" y="${y + 32}" width="36" height="14" rx="2" />
        <rect x="${x + 242}" y="${y + 104}" width="36" height="14" rx="2" />
        <!-- Subtle ceiling light nodes -->
        <circle cx="${x + 48}" cy="${y + 76}" r="3.5" fill="none" />
        <circle cx="${x + w - 48}" cy="${y + 76}" r="3.5" fill="none" />
      </g>
    `;
  }

  if (cfg.type === 'seminar') {
    // Seminar layout + central cassette AC icon + audio speaker corners
    return `
      <g class="pointer-events-none" stroke="${stroke}" fill="${fill}" stroke-width="1">
        <!-- Cassette AC unit (top-right corner) -->
        <rect x="${x + w - 44}" y="${y + 16}" width="26" height="26" rx="3" />
        <line x1="${x + w - 39}" y1="${y + 21}" x2="${x + w - 23}" y2="${y + 37}" />
        <line x1="${x + w - 23}" y1="${y + 21}" x2="${x + w - 39}" y2="${y + 37}" />
        <!-- Seminar side tables -->
        <rect x="${x + 22}" y="${y + 26}" width="18" height="96" rx="3" />
        <rect x="${x + w - 40}" y="${y + 58}" width="18" height="64" rx="3" />
        <!-- Ceiling light fixtures -->
        <circle cx="${x + 68}" cy="${y + 30}" r="3.5" fill="none" />
        <circle cx="${x + 68}" cy="${y + h - 30}" r="3.5" fill="none" />
      </g>
    `;
  }

  if (cfg.type === 'studio') {
    // Collaborative studio: round discussion pods + wall smart display + split AC
    return `
      <g class="pointer-events-none" stroke="${stroke}" fill="${fill}" stroke-width="1">
        <!-- Smart TV bar on west wall -->
        <line x1="${x + 7}" y1="${y + 42}" x2="${x + 7}" y2="${y + 110}" stroke="rgba(148,163,184,0.3)" stroke-width="2.5" />
        <!-- Collaborative round tables -->
        <circle cx="${x + 48}" cy="${y + 52}" r="16" />
        <circle cx="${x + 48}" cy="${y + 104}" r="16" />
        <circle cx="${x + w - 48}" cy="${y + 104}" r="16" />
        <!-- Split AC on south wall -->
        <rect x="${x + 128}" y="${y + h - 13}" width="44" height="9" rx="2" />
        <line x1="${x + 134}" y1="${y + h - 11}" x2="${x + 166}" y2="${y + h - 11}" stroke-dasharray="3 2" />
        <!-- Light fixtures -->
        <circle cx="${x + w - 48}" cy="${y + 42}" r="3.5" fill="none" />
      </g>
    `;
  }

  // Lab IoT: server racks along east wall + lab benches + dual AC
  return `
    <g class="pointer-events-none" stroke="${stroke}" fill="${fill}" stroke-width="1">
      <!-- Server & Oscilloscope Racks on east wall -->
      <rect x="${x + w - 34}" y="${y + 22}" width="22" height="32" rx="2" />
      <line x1="${x + w - 30}" y1="${y + 32}" x2="${x + w - 16}" y2="${y + 32}" />
      <line x1="${x + w - 30}" y1="${y + 42}" x2="${x + w - 16}" y2="${y + 42}" />
      <rect x="${x + w - 34}" y="${y + 62}" width="22" height="32" rx="2" />
      <line x1="${x + w - 30}" y1="${y + 72}" x2="${x + w - 16}" y2="${y + 72}" />
      <line x1="${x + w - 30}" y1="${y + 82}" x2="${x + w - 16}" y2="${y + 82}" />
      <!-- Lab workbench outlines -->
      <rect x="${x + 20}" y="${y + 32}" width="44" height="16" rx="2" />
      <rect x="${x + 20}" y="${y + 104}" width="44" height="16" rx="2" />
      <!-- Dual AC units along south wall -->
      <rect x="${x + 112}" y="${y + h - 13}" width="40" height="9" rx="2" />
      <rect x="${x + 216}" y="${y + h - 13}" width="40" height="9" rx="2" />
      <!-- Ceiling lights -->
      <circle cx="${x + 56}" cy="${y + 76}" r="3.5" fill="none" />
      <circle cx="${x + w - 58}" cy="${y + 116}" r="3.5" fill="none" />
    </g>
  `;
}

export class EnergyFloorPlanComponent {
  constructor(containerEl, { onSelectRoom }) {
    this.containerEl = containerEl;
    this.onSelectRoom = onSelectRoom;
    this.roomElements = new Map();
    this.selectedRoom = null;
    this.mounted = false;
  }

  mount() {
    if (!this.containerEl || this.mounted) return;

    const roomGroupsSvg = FLOORPLAN_ROOMS.map(cfg => {
      const { x, y, w, h } = cfg.rect;
      const cx = x + w / 2;
      const cy = y + h / 2;
      const mp = cfg.meterPos;

      return `
        <g
          class="en-svg-room cursor-pointer"
          data-room="${cfg.ruang}"
          role="button"
          tabindex="0"
          aria-pressed="false"
          aria-label="Pilih ${cfg.label} (${cfg.device_id})"
        >
          <!-- Soft heatmap radial glow fill -->
          <rect
            class="en-room-glow"
            x="${x + 2}" y="${y + 2}" width="${w - 4}" height="${h - 4}" rx="4"
            fill="url(#en-glow-offline)"
            opacity="0.7"
          />
          <!-- Tinted floor surface & dynamic status border -->
          <rect
            class="en-room-surface"
            x="${x}" y="${y}" width="${w}" height="${h}" rx="4"
            fill="rgba(71, 85, 105, 0.10)"
            stroke="#475569"
            stroke-width="1.5"
          />
          <!-- Active selection outer frame (hidden unless selected) -->
          <rect
            class="en-room-selection"
            x="${x - 3.5}" y="${y - 3.5}" width="${w + 7}" height="${h + 7}" rx="7"
            fill="none"
            stroke="#38bdf8"
            stroke-width="2"
            opacity="0"
          />
          <!-- Subtle architectural interior icons (AC, desks, racks, lights) -->
          ${buildInteriorBlueprintDetails(cfg)}
          <!-- Door swing opening -->
          ${buildDoorSwingSvg(cfg.door)}
          <!-- kWh Meter node marker near wall -->
          <g class="pointer-events-none">
            <rect x="${mp.x - 16}" y="${mp.y - 6}" width="32" height="12" rx="3" fill="#0b1323" stroke="#334155" stroke-width="1" />
            <text x="${mp.x}" y="${mp.y + 3}" text-anchor="middle" fill="#94a3b8" font-family="'IBM Plex Mono', monospace" font-size="7.5" font-weight="600">${cfg.device_id}</text>
          </g>
          <!-- Room center data overlay (Name, Power W, Status Pill) -->
          <g class="pointer-events-none">
            <text
              x="${cx}" y="${cy - 22}"
              text-anchor="middle"
              fill="#f8fafc"
              font-family="'IBM Plex Sans', system-ui, sans-serif"
              font-size="14"
              font-weight="600"
              letter-spacing="0.02em"
            >${cfg.codeLabel}</text>
            <text
              x="${cx}" y="${cy - 7}"
              text-anchor="middle"
              fill="#94a3b8"
              font-family="'IBM Plex Sans', system-ui, sans-serif"
              font-size="10"
            >${cfg.label}</text>
            <text
              class="en-room-power"
              x="${cx}" y="${cy + 20}"
              text-anchor="middle"
              fill="#e2e8f0"
              font-family="'IBM Plex Mono', monospace"
              font-size="20"
              font-weight="600"
            >-- W</text>
            <g transform="translate(${cx}, ${cy + 36})">
              <rect class="en-room-badge-bg" x="-44" y="-9" width="88" height="18" rx="9" fill="rgba(15, 23, 42, 0.85)" stroke="#475569" stroke-width="1" />
              <circle class="en-room-badge-dot" cx="-31" cy="0" r="3" fill="#64748b" />
              <text class="en-room-badge-text" x="4" y="3.5" text-anchor="middle" fill="#cbd5e1" font-family="'IBM Plex Mono', monospace" font-size="8.5" font-weight="600">OFFLINE</text>
            </g>
          </g>
        </g>
      `;
    }).join('');

    this.containerEl.innerHTML = `
      <svg
        id="en-floorplan-svg"
        viewBox="0 0 820 440"
        class="w-full h-auto block select-none"
        role="img"
        aria-label="Denah arsitektur interaktif Smart Energy Lantai 3 Gedung BSD-A"
      >
        <defs>
          <!-- Subtle architectural blueprint grid -->
          <pattern id="en-bp-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(148, 163, 184, 0.055)" stroke-width="1" />
          </pattern>
          <!-- Soft radial heatmap glows per status -->
          <radialGradient id="en-glow-normal" cx="50%" cy="52%" r="60%">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.24" />
            <stop offset="65%" stop-color="#0284c7" stop-opacity="0.06" />
            <stop offset="100%" stop-color="#0284c7" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="en-glow-waste" cx="50%" cy="52%" r="60%">
            <stop offset="0%" stop-color="#f59e0b" stop-opacity="0.30" />
            <stop offset="65%" stop-color="#d97706" stop-opacity="0.08" />
            <stop offset="100%" stop-color="#d97706" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="en-glow-high" cx="50%" cy="52%" r="60%">
            <stop offset="0%" stop-color="#f43f5e" stop-opacity="0.34" />
            <stop offset="65%" stop-color="#e11d48" stop-opacity="0.09" />
            <stop offset="100%" stop-color="#e11d48" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="en-glow-offline" cx="50%" cy="52%" r="60%">
            <stop offset="0%" stop-color="#64748b" stop-opacity="0.12" />
            <stop offset="100%" stop-color="#475569" stop-opacity="0" />
          </radialGradient>
        </defs>

        <!-- Blueprint backdrop -->
        <rect x="0" y="0" width="820" height="440" rx="8" fill="#080f1d" />
        <rect x="0" y="0" width="820" height="440" rx="8" fill="url(#en-bp-grid)" />

        <!-- Exterior Building Shell (BSD-A Lantai 3) -->
        <rect x="24" y="24" width="752" height="392" rx="6" fill="rgba(11, 19, 35, 0.85)" stroke="rgba(148, 163, 184, 0.28)" stroke-width="2" />

        <!-- West Wing Core: Tangga & Lift Shaft -->
        <g class="pointer-events-none">
          <rect x="34" y="36" width="46" height="152" rx="3" fill="rgba(15, 23, 42, 0.75)" stroke="rgba(148, 163, 184, 0.16)" stroke-width="1" />
          <!-- Staircase treads -->
          <g stroke="rgba(148, 163, 184, 0.2)" stroke-width="1">
            <line x1="40" y1="62" x2="74" y2="62" />
            <line x1="40" y1="72" x2="74" y2="72" />
            <line x1="40" y1="82" x2="74" y2="82" />
            <line x1="40" y1="92" x2="74" y2="92" />
            <line x1="40" y1="102" x2="74" y2="102" />
            <line x1="40" y1="112" x2="74" y2="112" />
          </g>
          <text x="57" y="138" text-anchor="middle" fill="#64748b" font-family="'IBM Plex Mono', monospace" font-size="8" font-weight="600">STAIR</text>

          <rect x="34" y="252" width="46" height="152" rx="3" fill="rgba(15, 23, 42, 0.75)" stroke="rgba(148, 163, 184, 0.16)" stroke-width="1" />
          <line x1="40" y1="262" x2="74" y2="310" stroke="rgba(148, 163, 184, 0.15)" stroke-width="1" />
          <line x1="74" y1="262" x2="40" y2="310" stroke="rgba(148, 163, 184, 0.15)" stroke-width="1" />
          <text x="57" y="344" text-anchor="middle" fill="#64748b" font-family="'IBM Plex Mono', monospace" font-size="8" font-weight="600">LIFT</text>
        </g>

        <!-- Central Corridor Zone -->
        <g class="pointer-events-none">
          <rect x="34" y="192" width="730" height="56" rx="2" fill="rgba(15, 23, 42, 0.55)" />
          <line x1="88" y1="220" x2="754" y2="220" stroke="rgba(56, 189, 248, 0.14)" stroke-width="1" stroke-dasharray="6 6" />
          <text x="196" y="223" text-anchor="middle" fill="#64748b" font-family="'IBM Plex Mono', monospace" font-size="9.5" letter-spacing="0.14em">KORIDOR UTAMA LT. 3</text>
          <text x="646" y="223" text-anchor="middle" fill="#64748b" font-family="'IBM Plex Mono', monospace" font-size="9.5" letter-spacing="0.14em">SAYAP TIMUR</text>
        </g>

        <!-- Electrical Feeder Bus Lines from MDP to kWh Meters -->
        <g class="pointer-events-none" fill="none" stroke-width="1.25" opacity="0.65">
          <path id="en-bus-r3012" d="M 410 220 L 280 220 L 280 190" stroke="#334155" />
          <path id="en-bus-r3013" d="M 410 220 L 526 220 L 526 190" stroke="#334155" />
          <path id="en-bus-r3017" d="M 410 220 L 280 220 L 280 250" stroke="#334155" />
          <path id="en-bus-lab-iot" d="M 410 220 L 526 220 L 526 250" stroke="#334155" />
        </g>

        <!-- Central MDP (Main Distribution Panel) Node -->
        <g class="pointer-events-none">
          <rect x="380" y="204" width="60" height="32" rx="6" fill="#0f172a" stroke="#38bdf8" stroke-opacity="0.55" stroke-width="1.25" />
          <text x="410" y="218" text-anchor="middle" fill="#38bdf8" font-family="'IBM Plex Mono', monospace" font-size="9" font-weight="600">MDP-3</text>
          <text x="410" y="229" text-anchor="middle" fill="#94a3b8" font-family="'IBM Plex Mono', monospace" font-size="7.5">PANEL</text>
        </g>

        <!-- Structural Divider Shaft Between West and East Rooms -->
        <g class="pointer-events-none" fill="rgba(30, 41, 59, 0.55)" stroke="rgba(148, 163, 184, 0.16)" stroke-width="1">
          <rect x="396" y="36" width="28" height="152" rx="2" />
          <rect x="396" y="252" width="28" height="152" rx="2" />
        </g>

        <!-- Interactive Rooms -->
        ${roomGroupsSvg}

        <!-- Subtle North Compass & Blueprint Scale Footer -->
        <g class="pointer-events-none" fill="#64748b" font-family="'IBM Plex Mono', monospace" font-size="8.5">
          <text x="795" y="42" text-anchor="middle" font-weight="600">N</text>
          <path d="M 795 48 L 791 58 L 795 55 L 799 58 Z" fill="#64748b" />
          <text x="36" y="431" fill="#475569">GEDUNG BSD-A · LANTAI 3 · 4 METER AKTIF</text>
          <text x="776" y="431" text-anchor="end" fill="#475569">KLIK RUANG UNTUK INSPEKSI DETAIL</text>
        </g>
      </svg>
    `;

    FLOORPLAN_ROOMS.forEach(cfg => {
      const el = this.containerEl.querySelector(`.en-svg-room[data-room="${cfg.ruang}"]`);
      if (!el) return;
      this.roomElements.set(cfg.ruang, el);

      const handleSelect = () => {
        if (typeof this.onSelectRoom === 'function') {
          this.onSelectRoom(cfg.ruang);
        }
      };

      el.addEventListener('click', handleSelect);
      el.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          handleSelect();
        }
      });
    });

    this.mounted = true;
  }

  update({ roomsMap, selectedRoom, roomFilter = 'all' }) {
    if (!this.mounted) this.mount();
    this.selectedRoom = selectedRoom;

    for (const cfg of FLOORPLAN_ROOMS) {
      const el = this.roomElements.get(cfg.ruang);
      if (!el) continue;

      const r = roomsMap.get(cfg.ruang);
      const statusKey = r?.visualStatus || 'offline';
      const meta = STATUS_META[statusKey] || STATUS_META.offline;
      const isSelected = selectedRoom === cfg.ruang;
      const isDimmed = roomFilter !== 'all' && roomFilter !== cfg.ruang;

      el.setAttribute('aria-pressed', String(isSelected));
      el.style.opacity = isDimmed ? '0.38' : '1';

      const surface = el.querySelector('.en-room-surface');
      const glow = el.querySelector('.en-room-glow');
      const selRing = el.querySelector('.en-room-selection');
      const powerText = el.querySelector('.en-room-power');
      const badgeBg = el.querySelector('.en-room-badge-bg');
      const badgeDot = el.querySelector('.en-room-badge-dot');
      const badgeText = el.querySelector('.en-room-badge-text');

      if (surface) {
        surface.setAttribute('fill', isSelected ? meta.fillHover : meta.fillTint);
        surface.setAttribute('stroke', meta.stroke);
        surface.setAttribute('stroke-width', isSelected ? '2.25' : '1.5');
      }
      if (glow) {
        glow.setAttribute('fill', `url(#${meta.glowId})`);
        glow.setAttribute('opacity', statusKey === 'offline' ? '0.45' : (isSelected ? '1' : '0.82'));
      }
      if (selRing) {
        selRing.setAttribute('stroke', meta.stroke);
        selRing.setAttribute('opacity', isSelected ? '0.9' : '0');
      }
      if (powerText) {
        powerText.textContent = r?.online ? `${Number(r.power_w || 0).toFixed(1)} W` : '0.0 W';
        powerText.setAttribute('fill', r?.online ? '#f8fafc' : '#64748b');
      }
      if (badgeBg) {
        badgeBg.setAttribute('stroke', meta.stroke);
      }
      if (badgeDot) {
        badgeDot.setAttribute('fill', meta.stroke);
      }
      if (badgeText) {
        badgeText.textContent = meta.shortLabel.toUpperCase();
        badgeText.setAttribute('fill', meta.textHex);
      }

      const busEl = this.containerEl.querySelector(`#en-bus-${cfg.ruang}`);
      if (busEl) {
        busEl.setAttribute('stroke', r?.online ? meta.stroke : '#334155');
        busEl.setAttribute('stroke-opacity', isDimmed ? '0.2' : (r?.online ? '0.7' : '0.35'));
      }
    }
  }
}
