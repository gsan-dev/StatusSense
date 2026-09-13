function statusLabel(status) {
  return { up: "Operativo", degraded: "Degradado", down: "Caído", paused: "Pausado", pending: "Pendiente" }[status] || status;
}

function scoreColor(score) {
  if (score === null || score === undefined) return "var(--gray)";
  if (score >= 80) return "var(--green)";
  if (score >= 60) return "var(--amber)";
  return "var(--red)";
}

async function loadStatusPage() {
  const grid = document.getElementById("status-grid");
  try {
    const data = await fetch("/api/status-page").then((r) => r.json());
    document.getElementById("generated-at").textContent = "Actualizado: " + new Date(data.generated_at).toLocaleString();

    if (!data.monitors.length) {
      grid.innerHTML = '<div class="empty">No hay servicios publicados todavía.</div>';
      return;
    }

    grid.innerHTML = data.monitors
      .map(
        (m) => `
        <div class="card">
          <div class="card-head">
            <h3>${m.name}</h3>
            <span class="badge ${m.status}"><span class="dot"></span>${statusLabel(m.status)}</span>
          </div>
          <div class="score-row">
            <span class="score" style="color:${scoreColor(m.health_score)}">${m.health_score ?? "–"}</span>
            <span class="score-label">/ 100</span>
          </div>
          <div class="score-bar"><div style="width:${m.health_score ?? 0}%; background:${scoreColor(m.health_score)}"></div></div>
          <div class="target" style="margin-top:8px">Uptime 24h: ${m.uptime_pct_24h ?? "–"}%</div>
        </div>`
      )
      .join("");
  } catch (err) {
    grid.innerHTML = '<div class="empty">No se pudo cargar el estado del servicio.</div>';
  }
}

loadStatusPage();
setInterval(loadStatusPage, 20000);
