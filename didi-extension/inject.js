/**
 * Se inyecta en el contexto de la página para interceptar fetch y XMLHttpRequest.
 * Detecta respuestas de getShops, newOrders y las envía al content script via customEvent.
 */
(function () {
  const CAPTURE_URLS = ["getShops", "newOrders", "dailyOrders", "getShopByID"];

  function shouldCapture(url) {
    if (!url || typeof url !== "string") return false;
    var u = url.toLowerCase();
    return u.indexOf("getshops") >= 0 || u.indexOf("neworders") >= 0 || u.indexOf("dailyorders") >= 0 || u.indexOf("getshopbyid") >= 0;
  }

  function getType(url) {
    var u = url.toLowerCase();
    if (u.indexOf("dailyorders") >= 0) return "dailyOrders";
    if (u.indexOf("getshopbyid") >= 0) return "getShopByID";
    if (u.indexOf("getshops") >= 0) return "getShops";
    if (u.indexOf("neworders") >= 0) return "newOrders";
    return "unknown";
  }

  function sendCapture(type, url, data) {
    document.dispatchEvent(
      new CustomEvent("didi-capture", {
        detail: { type, url, data },
      })
    );
  }

  // Interceptar fetch - getShops, newOrders, dailyOrders
  const origFetch = window.fetch;
  window.fetch = function (...args) {
    const input = args[0];
    let url = "";
    if (typeof input === "string") url = input;
    else if (input && input.url) url = input.url;
    else if (input && input instanceof Request) url = input.url;
    if (!shouldCapture(url)) return origFetch.apply(this, args);

    return origFetch.apply(this, args).then(async (response) => {
      const clone = response.clone();
      try {
        const ct = (response.headers.get("content-type") || "").toLowerCase();
        const text = await clone.text();
        const isJson = ct.includes("application/json") || /^\s*[{[]/.test(text);
        if (isJson && text) {
          const data = JSON.parse(text);
          sendCapture(getType(url), url, data);
        }
      } catch {}
      return response;
    });
  };

  // Interceptar XMLHttpRequest
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this._didiUrl = typeof url === "string" ? url : "";
    return origOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    const xhr = this;
    const url = xhr._didiUrl || "";
    if (shouldCapture(url)) {
      xhr.addEventListener("load", function () {
        try {
          const txt = xhr.responseText;
          const ct = (xhr.getResponseHeader("content-type") || "").toLowerCase();
          const isJson = ct.includes("application/json") || (txt && /^\s*[{[]/.test(txt));
          if (isJson && txt) {
            const data = JSON.parse(txt);
            sendCapture(getType(url), url, data);
          }
        } catch {}
      });
    }
    return origSend.apply(this, arguments);
  };
})();
