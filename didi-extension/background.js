/**
 * Service worker: recibe datos capturados y los envía al backend.
 * getShopByID -> POST /didi/sede-heartbeat (inmediato + cada 30 s con alarmas).
 * dailyOrders -> /didi/daily-orders-payload; resto -> /didi/capture.
 * La sede se guarda en storage y las alarmas siguen aunque el worker se duerma.
 */
const ALARM_HEARTBEAT = "sedeHeartbeat";
const HEARTBEAT_PERIOD_MINUTES = 0.5; // 30 segundos

function getBaseUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ backendUrl: "https://restaurant.reports.salchimonster.com" }, (o) => {
      resolve(String(o.backendUrl || "https://restaurant.reports.salchimonster.com").replace(/\/$/, ""));
    });
  });
}

async function sendSedeHeartbeat() {
  const { lastSedePayload } = await chrome.storage.local.get({ lastSedePayload: null });
  if (!lastSedePayload) return;
  try {
    const base = await getBaseUrl();
    const res = await fetch(`${base}/didi/sede-heartbeat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lastSedePayload),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) console.warn("[Didi Capture] sede-heartbeat:", json);
  } catch (err) {
    console.warn("[Didi Capture] sede-heartbeat error:", err);
  }
}

function startHeartbeatAlarm() {
  chrome.alarms.create(ALARM_HEARTBEAT, { periodInMinutes: HEARTBEAT_PERIOD_MINUTES });
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_HEARTBEAT) sendSedeHeartbeat();
});

// Al arrancar: si ya teníamos una sede guardada, reanudar el heartbeat (p. ej. tras reiniciar Chrome)
chrome.storage.local.get({ lastSedePayload: null }, (o) => {
  if (o.lastSedePayload) startHeartbeatAlarm();
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.action !== "sendToBackend" || !msg.type || !msg.data) {
    sendResponse({ ok: false, json: { error: "Invalid message" } });
    return true;
  }

  (async () => {
    try {
      const base = await getBaseUrl();
      const typeLower = String(msg.type).toLowerCase();
      const isDailyOrders = typeLower === "dailyorders";
      const isSedeHeartbeat = typeLower === "getshopbyid";

      if (isSedeHeartbeat) {
        await chrome.storage.local.set({ lastSedePayload: msg.data });
        startHeartbeatAlarm();
        const res = await fetch(`${base}/didi/sede-heartbeat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(msg.data),
        });
        const json = await res.json().catch(() => ({}));
        sendResponse({ ok: res.ok, json });
        return;
      }

      const url = isDailyOrders ? `${base}/didi/daily-orders-payload` : `${base}/didi/capture`;
      const body = isDailyOrders ? JSON.stringify(msg.data) : JSON.stringify({ type: msg.type, data: msg.data });

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      const json = await res.json().catch(() => ({}));
      sendResponse({ ok: res.ok, json });
    } catch (err) {
      sendResponse({ ok: false, json: { error: String(err?.message || err) } });
    }
  })();
  return true;
});
