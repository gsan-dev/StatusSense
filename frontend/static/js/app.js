const API = "/api";
let currentDetailId = null;

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2500);
}

function scoreColor(score) {
  if (score === null || score === undefined) return "var(--gray)";
  if (score >= 80) return "var(--green)";
  if (score >= 60) return "var(--amber)";
  return "var(--red)";
}

function statusLabel(status) {
  return { up: "Operativo", degraded: "Degradado", down: "Caído", paused: "Pausado", pending: "Pendiente" }[status] || status;
}

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ---------- Dashboard grid ----------

let activeFilter = "all";
let lastMonitors = [];

async function loadMonitors() {
  const grid = document.getElementById("monitor-grid");
  const summary = document.getElementById("summary");
  try {
    const monitors = await api("/monitors");
    lastMonitors = monitors;
    if (!monitors.length) {
      grid.innerHTML = '<div class="empty">Todavía no hay monitores. Pulsa "+ Añadir monitor" para crear el primero.</div>';
      summary.innerHTML = "";
      return;
    }
    const counts = { up: 0, degraded: 0, down: 0, paused: 0, pending: 0 };
    monitors.forEach((m) => { counts[m.status] = (counts[m.status] || 0) + 1; });

    renderFilters(summary, counts, monitors.length);
    renderGrid(grid, monitors);
  } catch (err) {
    grid.innerHTML = `<div class="empty">Error cargando monitores: ${escapeHtml(err.message)}</div>`;
  }
}

function renderFilters(summary, counts, total) {
  const chips = [
    { key: "all", label: `Todos`, count: total },
    { key: "up", label: statusLabel("up"), count: counts.up || 0 },
    { key: "degraded", label: statusLabel("degraded"), count: counts.degraded || 0 },
    { key: "down", label: statusLabel("down"), count: counts.down || 0 },
    { key: "paused", label: statusLabel("paused"), count: counts.paused || 0 },
  ].filter((c) => c.key === "all" || c.count > 0);

  summary.innerHTML = chips
    .map(
      (c) => `<button type="button" class="filter-chip ${c.key === activeFilter ? "active" : ""}" data-filter="${c.key}">${c.label} <span class="count">${c.count}</span></button>`
    )
    .join("");

  summary.querySelectorAll(".filter-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeFilter = btn.dataset.filter;
      renderFilters(summary, counts, total);
      renderGrid(document.getElementById("monitor-grid"), lastMonitors);
    });
  });
}

function renderGrid(grid, monitors) {
  const visible = activeFilter === "all" ? monitors : monitors.filter((m) => m.status === activeFilter);

  if (!visible.length) {
    grid.innerHTML = '<div class="empty">Ningún monitor coincide con este filtro.</div>';
    return;
  }

  grid.innerHTML = visible
    .map((m) => {
      const score = m.health_score ?? 0;
      return `
      <div class="card" data-id="${m.id}">
        <div class="card-head">
          <div>
            <h3>${escapeHtml(m.name)}</h3>
            <div class="target">${m.type.toUpperCase()} · ${escapeHtml(m.target)}</div>
          </div>
          <span class="badge ${m.status}"><span class="dot"></span>${statusLabel(m.status)}</span>
        </div>
        <div class="score-row">
          <span class="score" style="color:${scoreColor(m.health_score)}">${m.health_score ?? "–"}</span>
          <span class="score-label">/ 100 health score</span>
        </div>
        <div class="score-bar"><div style="width:${score}%; background:${scoreColor(m.health_score)}"></div></div>
      </div>`;
    })
    .join("");

  grid.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", () => openDetail(Number(card.dataset.id)));
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------- Detail modal ----------

async function openDetail(id) {
  currentDetailId = id;
  const overlay = document.getElementById("detail-overlay");
  const body = document.getElementById("detail-body");
  overlay.hidden = false;
  body.innerHTML = "<p>Cargando…</p>";

  const [monitor, checks, incidents] = await Promise.all([
    api(`/monitors/${id}`),
    api(`/monitors/${id}/checks?limit=100`),
    api(`/monitors/${id}/incidents`),
  ]);

  document.getElementById("detail-title").textContent = monitor.name;

  const orderedChecks = [...checks].reverse();

  body.innerHTML = `
    <div class="status-summary">
      <span>Estado: <strong style="color:${scoreColor(monitor.health_score)}">${statusLabel(monitor.status)}</strong></span>
      <span>Health score: <strong>${monitor.health_score ?? "–"}</strong></span>
      <span>Objetivo: ${escapeHtml(monitor.target)}</span>
      <span>Intervalo: ${monitor.interval_seconds}s</span>
    </div>
    <div class="section-title">Cuándo falló (últimas ${orderedChecks.length} comprobaciones)</div>
    ${renderHeatbar(orderedChecks)}
    <div class="section-title">Latencia reciente (ms)</div>
    ${renderLatencyChart(orderedChecks)}
    <div class="section-title">Incidentes</div>
    ${renderIncidents(incidents)}
  `;
}

function renderLatencyChart(orderedChecks) {
  const points = orderedChecks
    .map((c, i) => ({ i, v: c.latency_ms, t: c.timestamp }))
    .filter((p) => p.v !== null && p.v !== undefined);

  if (points.length < 2) {
    return '<p style="color:var(--text-dim); font-size:0.85rem">No hay suficiente latencia registrada todavía para dibujar un gráfico.</p>';
  }

  const w = 600, h = 160, padL = 42, padR = 10, padT = 10, padB = 22;
  const n = orderedChecks.length;
  const values = points.map((p) => p.v);
  let min = Math.min(...values), max = Math.max(...values);
  if (min === max) { min -= 10; max += 10; }
  const pad = (max - min) * 0.12;
  min = Math.max(0, min - pad);
  max = max + pad;

  const x = (i) => padL + (n === 1 ? 0 : (i / (n - 1)) * (w - padL - padR));
  const y = (v) => padT + (1 - (v - min) / (max - min)) * (h - padT - padB);

  let path = "", areaPath = "", started = false, lastPt = null;
  orderedChecks.forEach((c, i) => {
    if (c.latency_ms === null || c.latency_ms === undefined) { started = false; return; }
    const px = x(i), py = y(c.latency_ms);
    if (!started) {
      path += `M${px.toFixed(1)},${py.toFixed(1)} `;
      areaPath += `M${px.toFixed(1)},${(h - padB).toFixed(1)} L${px.toFixed(1)},${py.toFixed(1)} `;
      started = true;
    } else {
      path += `L${px.toFixed(1)},${py.toFixed(1)} `;
      areaPath += `L${px.toFixed(1)},${py.toFixed(1)} `;
    }
    lastPt = [px, py];
  });
  if (lastPt) areaPath += `L${lastPt[0].toFixed(1)},${(h - padB).toFixed(1)} Z`;

  const gridLines = [0, 0.5, 1]
    .map((f) => {
      const gy = padT + f * (h - padT - padB);
      const val = Math.round(max - f * (max - min));
      return `<line x1="${padL}" y1="${gy.toFixed(1)}" x2="${w - padR}" y2="${gy.toFixed(1)}" stroke="var(--border)" stroke-width="1"/>
              <text x="${padL - 6}" y="${(gy + 3).toFixed(1)}" text-anchor="end" font-size="10" fill="var(--text-dim)">${val}</text>`;
    })
    .join("");

  const firstLabel = new Date(orderedChecks[0].timestamp).toLocaleTimeString();
  const lastLabel = new Date(orderedChecks[orderedChecks.length - 1].timestamp).toLocaleTimeString();

  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%; height:auto; display:block; overflow:visible" role="img" aria-label="Latencia reciente">
    ${gridLines}
    <path d="${areaPath}" fill="var(--blue)" opacity="0.12"/>
    <path d="${path}" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    ${lastPt ? `<circle cx="${lastPt[0].toFixed(1)}" cy="${lastPt[1].toFixed(1)}" r="3.4" fill="var(--blue)" stroke="var(--bg-card)" stroke-width="2"/>` : ""}
    <text x="${padL}" y="${h - 4}" font-size="10" fill="var(--text-dim)">${firstLabel}</text>
    <text x="${w - padR}" y="${h - 4}" text-anchor="end" font-size="10" fill="var(--text-dim)">${lastLabel}</text>
  </svg>`;
}

function renderHeatbar(orderedChecks) {
  if (!orderedChecks.length) {
    return '<p style="color:var(--text-dim); font-size:0.85rem">Todavía no hay comprobaciones registradas.</p>';
  }
  const cells = orderedChecks
    .map((c) => {
      const time = new Date(c.timestamp).toLocaleString();
      const detail = c.success
        ? `${time} · OK · ${c.latency_ms != null ? c.latency_ms + "ms" : "–"}`
        : `${time} · FALLO · ${c.error_message || (c.http_status ? "HTTP " + c.http_status : "sin respuesta")}`;
      return `<div class="heat-cell ${c.success ? "" : "fail"}" title="${escapeHtml(detail)}"></div>`;
    })
    .join("");
  const first = new Date(orderedChecks[0].timestamp).toLocaleTimeString();
  const last = new Date(orderedChecks[orderedChecks.length - 1].timestamp).toLocaleTimeString();
  return `<div class="heatbar">${cells}</div><div class="heatbar-caption"><span>${first}</span><span>${last}</span></div>`;
}

function renderIncidents(incidents) {
  if (!incidents.length) return '<p style="color:var(--text-dim)">Sin incidentes registrados.</p>';
  return `
    <table>
      <thead><tr><th>Inicio</th><th>Fin</th><th>Tipo</th><th>Score mínimo</th></tr></thead>
      <tbody>
        ${incidents
          .map(
            (i) => `<tr>
              <td>${new Date(i.started_at).toLocaleString()}</td>
              <td>${i.resolved_at ? new Date(i.resolved_at).toLocaleString() : "En curso"}</td>
              <td><span class="incident-tag ${i.incident_type}">${i.incident_type === "sudden_outage" ? "Caída súbita" : "Degradación progresiva"}</span></td>
              <td>${i.min_health_score ?? "–"}</td>
            </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

document.getElementById("detail-close").addEventListener("click", () => {
  document.getElementById("detail-overlay").hidden = true;
  currentDetailId = null;
});

document.getElementById("detail-delete").addEventListener("click", async () => {
  if (!currentDetailId) return;
  if (!confirm("¿Eliminar este monitor? Se perderá su histórico.")) return;
  await api(`/monitors/${currentDetailId}`, { method: "DELETE" });
  document.getElementById("detail-overlay").hidden = true;
  toast("Monitor eliminado");
  loadMonitors();
});

document.getElementById("detail-edit").addEventListener("click", async () => {
  if (!currentDetailId) return;
  const monitor = await api(`/monitors/${currentDetailId}`);
  openForm(monitor);
});

document.getElementById("detail-check-now").addEventListener("click", async (e) => {
  if (!currentDetailId) return;
  e.target.disabled = true;
  try {
    await api(`/monitors/${currentDetailId}/check-now`, { method: "POST" });
    toast("Comprobación ejecutada");
    await openDetail(currentDetailId);
    loadMonitors();
  } catch (err) {
    toast("Error: " + err.message);
  } finally {
    e.target.disabled = false;
  }
});

document.getElementById("detail-reset").addEventListener("click", async () => {
  if (!currentDetailId) return;
  if (!confirm("¿Reiniciar el histórico de este monitor? Se borrarán sus comprobaciones, health scores e incidentes (la configuración del monitor se mantiene).")) return;
  await api(`/monitors/${currentDetailId}/history`, { method: "DELETE" });
  toast("Histórico reiniciado");
  await openDetail(currentDetailId);
  loadMonitors();
});

// ---------- Create/edit form ----------

function openForm(monitor) {
  document.getElementById("form-overlay").hidden = false;
  document.getElementById("form-title").textContent = monitor ? "Editar monitor" : "Nuevo monitor";
  document.getElementById("f-id").value = monitor ? monitor.id : "";
  document.getElementById("f-name").value = monitor ? monitor.name : "";
  document.getElementById("f-type").value = monitor ? monitor.type : "http";
  document.getElementById("f-target").value = monitor ? monitor.target : "";
  document.getElementById("f-interval").value = monitor ? monitor.interval_seconds : 60;
  document.getElementById("f-timeout").value = monitor ? monitor.timeout_seconds : 10;
  document.getElementById("f-uptime-weight").value = monitor ? monitor.uptime_weight : 0.5;
  document.getElementById("f-degradation-weight").value = monitor ? monitor.degradation_weight : 0.3;
  document.getElementById("f-variance-weight").value = monitor ? monitor.variance_weight : 0.2;
  document.getElementById("f-active").value = monitor ? String(monitor.active) : "true";
}

document.getElementById("btn-add-monitor").addEventListener("click", () => openForm(null));
document.getElementById("form-close").addEventListener("click", () => {
  document.getElementById("form-overlay").hidden = true;
});

document.getElementById("monitor-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("f-id").value;
  const payload = {
    name: document.getElementById("f-name").value,
    type: document.getElementById("f-type").value,
    target: document.getElementById("f-target").value,
    interval_seconds: Number(document.getElementById("f-interval").value),
    timeout_seconds: Number(document.getElementById("f-timeout").value),
    uptime_weight: Number(document.getElementById("f-uptime-weight").value),
    degradation_weight: Number(document.getElementById("f-degradation-weight").value),
    variance_weight: Number(document.getElementById("f-variance-weight").value),
    active: document.getElementById("f-active").value === "true",
  };
  try {
    if (id) {
      await api(`/monitors/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      toast("Monitor actualizado");
    } else {
      await api("/monitors", { method: "POST", body: JSON.stringify(payload) });
      toast("Monitor creado");
    }
    document.getElementById("form-overlay").hidden = true;
    document.getElementById("detail-overlay").hidden = true;
    loadMonitors();
  } catch (err) {
    toast("Error: " + err.message);
  }
});

// ---------- Notifications ----------

document.getElementById("btn-notifications").addEventListener("click", async () => {
  document.getElementById("notif-overlay").hidden = false;
  await renderNotifChannels();
});
document.getElementById("notif-close").addEventListener("click", () => {
  document.getElementById("notif-overlay").hidden = true;
});

document.getElementById("n-type").addEventListener("change", (e) => {
  const isTelegram = e.target.value === "telegram";
  document.getElementById("n-config-telegram").style.display = isTelegram ? "block" : "none";
  document.getElementById("n-config-webhook").style.display = isTelegram ? "none" : "block";
});

async function renderNotifChannels() {
  const list = document.getElementById("notif-list");
  const channels = await api("/notifications");
  if (!channels.length) {
    list.innerHTML = '<p style="color:var(--text-dim)">Sin canales configurados.</p>';
    return;
  }
  list.innerHTML = channels
    .map(
      (c) => `<div style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border)">
        <span>${c.type === "telegram" ? "📨 Telegram" : "🪝 Webhook"} — ${escapeHtml(c.name || "sin nombre")}</span>
        <span>
          <button class="secondary" data-test-id="${c.id}">Probar</button>
          <button class="danger" data-channel-id="${c.id}">Eliminar</button>
        </span>
      </div>`
    )
    .join("");
  list.querySelectorAll("button[data-channel-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/notifications/${btn.dataset.channelId}`, { method: "DELETE" });
      renderNotifChannels();
    });
  });
  list.querySelectorAll("button[data-test-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "Enviando…";
      try {
        const result = await api(`/notifications/${btn.dataset.testId}/test`, { method: "POST" });
        toast(result.success ? "Notificación de prueba enviada" : "No se pudo enviar: revisa la configuración del canal");
      } catch (err) {
        toast("Error: " + err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = "Probar";
      }
    });
  });
}

document.getElementById("notif-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const type = document.getElementById("n-type").value;
  const name = document.getElementById("n-name").value;
  const config =
    type === "telegram"
      ? { bot_token: document.getElementById("n-bot-token").value, chat_id: document.getElementById("n-chat-id").value }
      : { url: document.getElementById("n-url").value };
  await api("/notifications", { method: "POST", body: JSON.stringify({ type, name, config, active: true }) });
  toast("Canal añadido");
  e.target.reset();
  renderNotifChannels();
});

// ---------- Export / import ----------

document.getElementById("btn-export").addEventListener("click", async () => {
  const bundle = await api("/export");
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "statussense-config.json";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("btn-import").addEventListener("click", () => {
  document.getElementById("import-overlay").hidden = false;
});
document.getElementById("import-close").addEventListener("click", () => {
  document.getElementById("import-overlay").hidden = true;
});
document.getElementById("import-submit").addEventListener("click", async () => {
  try {
    const bundle = JSON.parse(document.getElementById("import-json").value);
    const result = await api("/import", { method: "POST", body: JSON.stringify(bundle) });
    toast(`Importados ${result.monitors_imported} monitores y ${result.channels_imported} canales`);
    document.getElementById("import-overlay").hidden = true;
    loadMonitors();
  } catch (err) {
    toast("JSON inválido o error al importar");
  }
});

// ---------- Live updates via WebSocket ----------

function connectWebSocket() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${location.host}/ws/live`);
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (["check", "incident_opened", "incident_resolved"].includes(msg.type)) {
      loadMonitors();
      if (currentDetailId && msg.monitor_id === currentDetailId) {
        openDetail(currentDetailId);
      }
    }
  };
  ws.onclose = () => setTimeout(connectWebSocket, 3000);
}

loadMonitors();
setInterval(loadMonitors, 15000);
connectWebSocket();
