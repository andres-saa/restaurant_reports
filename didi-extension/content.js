/**
 * Content script: escucha didi-capture (de inject.js en world MAIN) y envía al backend.
 * inject.js corre en world MAIN a document_start para interceptar fetch/XHR antes que la página.
 */
(function () {
  async function sendToBackend(type, data) {
    try {
      const result = await chrome.runtime.sendMessage({
        action: "sendToBackend",
        type,
        data,
      });
      return result || { ok: false, json: { error: "No response" } };
    } catch (err) {
      console.warn("[Didi Capture] Error enviando al backend:", err);
      return { ok: false, json: { error: String(err?.message || err) } };
    }
  }

  document.addEventListener("didi-capture", async (e) => {
    const { type, url, data } = e.detail || {};
    if (!type || !data) return;

    try {
      const result = await sendToBackend(type, data);
      console.log("[Didi Capture] " + type + " -> backend:", result.ok ? "OK" : "Error", result.json);
      // Solo guardar lastCapture para dailyOrders/getShops/newOrders; no para getShopByID (heartbeat)
      const typeLower = String(type).toLowerCase();
      if (typeLower !== "getshopbyid") {
        chrome.storage.local.set({ lastCapture: { type, ok: result.ok, at: Date.now() } });
      }
    } catch (err) {
      console.warn("[Didi Capture] Error:", err);
    }
  });
})();
