/* Copperstate Tackle sale bubble — shared widget for b4u.fish and b4ufish.com
 * Reads https://b4u.fish/copperstate-sale.json (updated twice daily by the
 * lake-report-v2 scheduled task). Shows a small, dismissible badge ONLY while
 * a sale is active and not past its end date. Self-contained, Shadow-DOM
 * isolated, no dependencies. Safe to include on any page:
 *     <script src="https://b4u.fish/cst-sale-bubble.js" defer></script>
 */
(function () {
  "use strict";
  if (window.__cstSaleBubbleLoaded) return;
  window.__cstSaleBubbleLoaded = true;

  var DATA_URL = "https://b4u.fish/copperstate-sale.json";
  var SHOP_URL_FALLBACK = "https://copperstatetackle.com";

  // ---- Phoenix-local "today" (MST, UTC-7, no DST) as YYYY-MM-DD ----
  function phoenixToday() {
    var now = new Date();
    var mst = new Date(now.getTime() - 7 * 60 * 60 * 1000); // shift to UTC-7
    return mst.toISOString().slice(0, 10);
  }

  function saleIsLive(d) {
    if (!d || d.active !== true) return false;
    // If an end date is published, hide once we're past it (Phoenix local).
    if (d.end) {
      try {
        if (phoenixToday() > String(d.end).slice(0, 10)) return false;
      } catch (e) {}
    }
    return true;
  }

  function fetchSale() {
    // Cache-bust so the service worker / CDN can't serve a stale status.
    return fetch(DATA_URL + "?t=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function buildBadge(d) {
    var percent = d.percent != null ? String(d.percent) : "";
    var occasion = (d.headline || d.holiday || "Sale").toString();
    var shopUrl = d.url || SHOP_URL_FALLBACK;
    // Per-sale signature so a NEW sale re-shows even if a prior one was dismissed.
    var sig = "cst_sale_dismiss::" + percent + "::" + (d.end || "") + "::" + occasion;
    try { if (localStorage.getItem(sig) === "1") return; } catch (e) {}

    var host = document.createElement("div");
    host.id = "cst-sale-bubble-host";
    host.style.cssText =
      "position:fixed;right:16px;bottom:16px;z-index:2147483000;" +
      "max-width:calc(100vw - 32px);";
    var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

    var headline = (percent ? percent + "% OFF" : "On Sale") +
      (occasion ? " · " + occasion : "");

    root.innerHTML =
      '<style>' +
      ':host,*{box-sizing:border-box;}' +
      '.wrap{font-family:"Oswald",system-ui,-apple-system,Segoe UI,Roboto,sans-serif;' +
        'animation:cstIn .45s cubic-bezier(.22,1,.36,1) both;}' +
      '@keyframes cstIn{from{opacity:0;transform:translateY(14px) scale(.96);}to{opacity:1;transform:none;}}' +
      '.card{position:relative;display:flex;align-items:center;gap:11px;' +
        'text-decoration:none;color:#0a1420;' +
        'background:linear-gradient(135deg,#ffd23f 0%,#ff8a00 100%);' +
        'border:1px solid rgba(0,0,0,.12);border-radius:14px;' +
        'padding:11px 38px 11px 13px;' +
        'box-shadow:0 10px 28px rgba(0,0,0,.32),0 2px 6px rgba(0,0,0,.18);' +
        'transition:transform .15s ease,box-shadow .15s ease;cursor:pointer;}' +
      '.card:hover{transform:translateY(-2px);box-shadow:0 14px 34px rgba(0,0,0,.40),0 3px 8px rgba(0,0,0,.22);}' +
      '.card:focus-visible{outline:3px solid #0a1420;outline-offset:2px;}' +
      '.emoji{font-size:26px;line-height:1;filter:drop-shadow(0 1px 1px rgba(0,0,0,.25));}' +
      '.txt{display:flex;flex-direction:column;line-height:1.15;}' +
      '.brand{font-weight:600;font-size:11px;letter-spacing:.06em;text-transform:uppercase;opacity:.78;}' +
      '.deal{font-weight:600;font-size:16px;letter-spacing:.01em;}' +
      '.cta{font-weight:500;font-size:11px;letter-spacing:.04em;opacity:.82;margin-top:1px;}' +
      '.x{position:absolute;top:5px;right:6px;width:20px;height:20px;border:0;' +
        'background:rgba(0,0,0,.10);color:#0a1420;border-radius:50%;cursor:pointer;' +
        'font-size:13px;line-height:20px;text-align:center;padding:0;' +
        'transition:background .15s ease;}' +
      '.x:hover{background:rgba(0,0,0,.22);}' +
      '@media (max-width:480px){.deal{font-size:15px;}.emoji{font-size:23px;}}' +
      '@media (prefers-reduced-motion:reduce){.wrap{animation:none;}}' +
      '</style>' +
      '<div class="wrap">' +
        '<a class="card" href="' + shopUrl + '" target="_blank" rel="noopener noreferrer" ' +
            'aria-label="Copperstate Tackle ' + headline + ' — shop the sale">' +
          '<span class="emoji" aria-hidden="true">🎣</span>' +
          '<span class="txt">' +
            '<span class="brand">Copperstate Tackle</span>' +
            '<span class="deal">' + headline + '</span>' +
            '<span class="cta">Shop the sale →</span>' +
          '</span>' +
        '</a>' +
        '<button class="x" type="button" aria-label="Dismiss">✕</button>' +
      '</div>';

    var closeBtn = root.querySelector(".x");
    if (closeBtn) {
      closeBtn.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        try { localStorage.setItem(sig, "1"); } catch (e) {}
        host.remove();
      });
    }
    document.body.appendChild(host);
  }

  function start() {
    fetchSale().then(function (d) {
      if (saleIsLive(d)) buildBadge(d);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
