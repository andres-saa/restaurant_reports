const statusEl = document.getElementById("status");
const statusText = document.getElementById("statusText");
const sedeStatusEl = document.getElementById("sedeStatus");
const sedeStatusText = document.getElementById("sedeStatusText");
const backendInput = document.getElementById("backendUrl");
const saveBtn = document.getElementById("save");

function setStatus(message, type = "idle") {
  statusText.textContent = message;
  statusEl.className = "status " + type;
}

function setSedeStatus(message, type) {
  sedeStatusText.textContent = message;
  sedeStatusEl.className = "status " + type;
  sedeStatusEl.style.display = "block";
}

saveBtn.addEventListener("click", async () => {
  const url = backendInput.value.trim();
  if (!url) {
    setStatus("Escribe una URL antes de guardar.", "error");
    return;
  }
  try {
    await chrome.storage.sync.set({ backendUrl: url });
    setStatus("URL guardada: " + url, "ok");
  } catch (e) {
    setStatus("Error al guardar: " + (e.message || "desconocido"), "error");
  }
});

async function init() {
  const { backendUrl } = await chrome.storage.sync.get({
    backendUrl: "https://restaurant.reports.salchimonster.com",
  });
  backendInput.value = backendUrl || "";
  backendInput.placeholder = "https://restaurant.reports.salchimonster.com";

  const { lastSedePayload, lastCapture } = await chrome.storage.local.get({
    lastSedePayload: null,
    lastCapture: null,
  });

  // Sede: siempre que tengamos última sede detectada = "Conectada, reportando cada 30 s"
  if (lastSedePayload && lastSedePayload.data) {
    const shopName = (lastSedePayload.data.shopName || lastSedePayload.data.shopId || "Sede").trim();
    setSedeStatus("Sede: " + shopName + " — Reportando cada 30 s", "ok");
  } else {
    sedeStatusEl.style.display = "none";
  }

  // Última captura: solo dailyOrders/getShops/newOrders (no heartbeat)
  if (lastCapture && String(lastCapture.type).toLowerCase() !== "getshopbyid") {
    const time = lastCapture.at ? new Date(lastCapture.at).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) : "";
    const ok = lastCapture.ok ? "Órdenes/captura: última OK" : "Órdenes/captura: última falló";
    setStatus(time ? ok + " (" + time + ")" : ok, lastCapture.ok ? "ok" : "error");
  } else {
    setStatus("Extensión activa. Envía al backend al detectar órdenes o sedes.", "idle");
  }
}

init();
