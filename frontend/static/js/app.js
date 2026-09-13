const API = "/api";
let currentDetailId = null;
let detailChart = null;

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

async function loadMonitors() {
  const grid = document.getElementById("monitor-grid");
  const summary = document.getElementById("summary");
  try {
    const monitors = await api("/monitors");
    if (!monitors.length) {
      grid.innerHTML = '<div class="empty">Todavía no hay monitores. Pulsa "+ Añadir monitor" para crear el primero.</div>';
      summary.innerHTML = "";
      return;
    }
    const counts = { up: 0, degraded: 0, down: 0, paused: 0, pending: 0 };
    grid.innerHTML = monitors
      .map((m) => {
        counts[m.status] = (counts[m.status] || 0) + 1;
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

    summary.innerHTML = Object.entries(counts)
      .filter(([, c]) => c > 0)
      .map(([k, c]) => `${c} ${statusLabel(k).toLowerCase()}`)
      .join(" · ");

    grid.querySelectorAll(".card").forEach((card) => {
      card.addEventListener("click", () => openDetail(Number(card.dataset.id)));
    });
  } catch (err) {
    grid.innerHTML = `<div class="empty">Error cargando monitores: ${escapeHtml(err.message)}</div>`;
  }
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
    api(`/monitors/${id}/checks?limit=50`),
    api(`/monitors/${id}/incidents`),
  ]);

  document.getElementById("detail-title").textContent = monitor.name;

  const orderedChecks = [...checks].reverse();
  const labels = orderedChecks.map((c) => new Date(c.timestamp).toLocaleTimeString());
  const latencies = orderedChecks.map((c) => c.latency_ms);

  body.innerHTML = `
    <div class="status-summary">
      <span>Estado: <strong style="color:${scoreColor(monitor.health_score)}">${statusLabel(monitor.status)}</strong></span>
      <span>Health score: <strong>${monitor.health_score ?? "–"}</strong></span>
      <span>Objetivo: ${escapeHtml(monitor.target)}</span>
      <span>Intervalo: ${monitor.interval_seconds}s</span>
    </div>
    <div class="section-title">Latencia reciente</div>
    <canvas id="detail-chart" height="120"></canvas>
    <div class="section-title">Incidentes</div>
    ${renderIncidents(incidents)}
  `;

  const ctx = document.getElementById("detail-chart");
  if (detailChart) detailChart.destroy();
  detailChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Latencia (ms)",
          data: latencies,
          borderColor: "#4a90e2",
          backgroundColor: "rgba(74,144,226,0.1)",
          spanGaps: true,
          tension: 0.25,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#93a0bb" } } },
      scales: {
        x: { ticks: { color: "#93a0bb", maxTicksLimit: 8 }, grid: { color: "#2a344c" } },
        y: { ticks: { color: "#93a0bb" }, grid: { color: "#2a344c" } },
      },
    },
  });
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
        <button class="danger" data-channel-id="${c.id}">Eliminar</button>
      </div>`
    )
    .join("");
  list.querySelectorAll("button[data-channel-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/notifications/${btn.dataset.channelId}`, { method: "DELETE" });
      renderNotifChannels();
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
