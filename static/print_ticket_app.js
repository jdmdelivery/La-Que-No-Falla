/**
 * Impresión térmica 58mm: ESC/POS (base64) en APK / HTML en navegador.
 */
(function () {
  function normalizarTexto(texto) {
    return String(texto == null ? "" : texto).replace(/\r\n/g, "\n");
  }

  function extraerTicketId(texto) {
    var m = String(texto || "").match(/ticket\s*[:#]?\s*(\d+)/i);
    if (m) return m[1];
    var el = document.querySelector("[data-ticket-id]");
    if (el) return el.getAttribute("data-ticket-id") || "";
    var path = window.location.pathname || "";
    var m2 = path.match(/\/imprimir_pago\/(\d+)/) ||
      path.match(/\/ticket\/(\d+)/);
    return m2 ? m2[1] : "";
  }

  function obtenerEscPosB64() {
    var el = document.querySelector("[data-escpos-b64]");
    if (!el) return "";
    return String(el.getAttribute("data-escpos-b64") || "").trim();
  }

  function obtenerContenidoHtmlTicket() {
    var box = document.querySelector(".ticket-thermal") || document.querySelector(".ticket");
    if (!box) return "";
    var clone = box.cloneNode(true);
    var rm = clone.querySelectorAll(
      ".no-print, button, .btn, #printBtn, .btn-print-top, pre[data-print-text]"
    );
    for (var i = 0; i < rm.length; i++) {
      rm[i].parentNode.removeChild(rm[i]);
    }
    return clone.innerHTML;
  }

  window.__onAndroidPrintResult = function (result) {
    var ok = result && result.ok;
    var msg = (result && result.message) || "";
    var imp = (result && result.impresora) || "";
    if (ok) {
      console.log("[PRINT_OK] impresora=" + imp + " " + msg);
      return;
    }
    console.error("[PRINT_ERROR] mensaje=" + msg + " impresora=" + imp);
    var box = document.getElementById("printErrorBox");
    if (box) {
      box.style.display = "block";
      box.textContent = "Error imprimiendo: " + msg;
    }
  };

  window.ticketPlainFromEl = function (id) {
    var el = typeof id === "string" ? document.getElementById(id) : id;
    if (!el) return "";
    return normalizarTexto(el.textContent || "");
  };

  window.textoPlanoDesdeHtml = function (html) {
    var div = document.createElement("div");
    div.innerHTML = String(html || "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/div>/gi, "\n")
      .replace(/<\/p>/gi, "\n")
      .replace(/<\/tr>/gi, "\n");
    return normalizarTexto(div.textContent || "")
      .split("\n")
      .map(function (linea) {
        return linea.replace(/[ \t]+$/g, "");
      })
      .join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  };

  window.formatearHoraCompacta = function (texto) {
    var s = String(texto == null ? "" : texto);
    return s.replace(/\b(\d{1,2})(\d{2})(am|pm)\b/gi, function (_m, h, mi, ap) {
      return parseInt(h, 10) + ":" + mi + " " + String(ap).toUpperCase();
    });
  };

  window.imprimirTicket = function (texto) {
    texto = normalizarTexto(texto);
    var ticketId = extraerTicketId(texto);
    var escposB64 = obtenerEscPosB64();
    var impresora = "Bluetooth/ESC-POS";

    console.log(
      "[PRINT_START] ticket_id=" + (ticketId || "—") +
      " contenido_length=" + (escposB64 ? escposB64.length : texto.length) +
      " impresora=" + impresora +
      " modo=" + (escposB64 ? "escpos_b64" : "texto")
    );

    if (window.Android) {
      if (escposB64 && typeof Android.printEscPosBase64 === "function") {
        console.log("Imprimiendo ESC/POS base64 vía Android.printEscPosBase64");
        Android.printEscPosBase64(escposB64, ticketId || "");
        return;
      }
      if (typeof Android.printTicket === "function") {
        console.log("Imprimiendo texto vía Android.printTicket");
        Android.printTicket(texto, ticketId || "");
        return;
      }
      if (typeof Android.print === "function") {
        console.log("Imprimiendo texto vía Android.print");
        Android.print(texto);
        return;
      }
      if (typeof Android.logPrint === "function") {
        Android.logPrint("JS", "[PRINT_START] ticket_id=" + ticketId + " len=" + texto.length);
      }
    }

    var htmlTicket = obtenerContenidoHtmlTicket();
    if (!htmlTicket && (!texto || !texto.trim())) {
      var errEmpty = "El ticket está vacío (contenido_length=0)";
      console.error("[PRINT_ERROR] mensaje=" + errEmpty);
      alert("Error imprimiendo:\n" + errEmpty);
      return;
    }

    console.log("Modo navegador (sin Android.print)");
    var win = window.open("", "", "width=240,height=700");
    if (!win || !win.document) {
      console.error("[PRINT_ERROR] mensaje=No se pudo abrir ventana de impresión");
      return;
    }
    var cuerpo = htmlTicket
      ? htmlTicket
      : "<pre>" + texto.replace(/[&<>]/g, function (c) {
          return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c];
        }) + "</pre>";
    win.document.write(
      "<!DOCTYPE html><html><head><meta charset='utf-8'>" +
      "<meta name='viewport' content='width=58mm'>" +
      "<link rel='stylesheet' href='/static/ticket_thermal.css'></head>" +
      "<body class='ticket-body'><div class='ticket ticket-thermal'>" +
      cuerpo +
      "</div></body></html>"
    );
    win.document.close();
    win.focus();
    win.print();
  };

  window.printTicketApp = window.imprimirTicket;

  window.conectarImpresora = function () {
    console.log("Intentando conectar impresora...");
    if (window.Android && typeof Android.connect === "function") {
      Android.connect();
    }
  };

  window.generarTicket = window.generarTicket || function () {
    var pre = document.getElementById("reciboTextoPlano");
    if (pre && pre.textContent && pre.textContent.trim()) {
      return window.ticketPlainFromEl(pre);
    }
    var htmlBox = document.querySelector(".ticket-thermal") || document.querySelector(".ticket");
    if (htmlBox) {
      var plain = window.textoPlanoDesdeHtml(obtenerContenidoHtmlTicket());
      if (plain) return plain;
    }
    var esc = obtenerEscPosB64();
    if (esc) {
      var el = document.querySelector("[data-print-text]") || document.getElementById("reciboTextoPlano");
      if (el) return window.ticketPlainFromEl(el);
    }
    return "";
  };

  window.imprimir = window.imprimir || function () {
    window.imprimirTicket(window.generarTicket());
  };

  function staticAssetVersion() {
    if (window.__STATIC_ASSET_V__) return window.__STATIC_ASSET_V__;
    var meta = document.querySelector('meta[name="static-asset-version"]');
    return (meta && meta.content) || "20260622";
  }

  function removeDuplicateThemeLinks() {
    if (!document || !document.head) return;
    var seen = {};
    var links = document.head.querySelectorAll('link[rel="stylesheet"]');
    for (var i = 0; i < links.length; i++) {
      var href = String(links[i].getAttribute("href") || "");
      if (
        href.indexOf("/static/css/ui_modern.css") === -1 &&
        href.indexOf("/static/css/venta_premium.css") === -1 &&
        href.indexOf("/static/css/ranking_ticker.css") === -1
      ) {
        continue;
      }
      var base = href.split("?")[0];
      if (links[i].id && (links[i].id === "app-css-ui-modern" || links[i].id === "app-css-venta-premium" || links[i].id === "app-css-ranking-ticker")) {
        seen[base] = links[i];
        continue;
      }
      if (seen[base]) {
        if (links[i].parentNode) links[i].parentNode.removeChild(links[i]);
      } else {
        seen[base] = links[i];
      }
    }
    ["ui-modern-theme-css", "venta-premium-theme-css", "ranking-ticker-theme-css"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    });
  }

  function injectModernThemeCss() {
    if (!document || !document.head) return;
    removeDuplicateThemeLinks();
    var v = staticAssetVersion();
    var defs = [
      { id: "app-css-ui-modern", href: "/static/css/ui_modern.css?v=" + v },
      { id: "app-css-venta-premium", href: "/static/css/venta_premium.css?v=" + v },
      { id: "app-css-ranking-ticker", href: "/static/css/ranking_ticker.css?v=" + v }
    ];
    var pending = 0;
    function doneOne() {
      pending--;
      if (pending <= 0 && typeof window.__restartRankingTicker === "function") {
        window.__restartRankingTicker();
      }
    }
    defs.forEach(function (def) {
      var cur = document.getElementById(def.id);
      if (cur && cur.getAttribute("href") === def.href) return;
      if (cur && cur.parentNode) cur.parentNode.removeChild(cur);
      pending++;
      var link = document.createElement("link");
      link.id = def.id;
      link.rel = "stylesheet";
      link.href = def.href;
      link.onload = doneOne;
      link.onerror = doneOne;
      document.head.appendChild(link);
    });
    if (pending === 0 && typeof window.__restartRankingTicker === "function") {
      window.__restartRankingTicker();
    }
  }

  function isTicketOrPrintPath(pathname) {
    var p = String(pathname || "").toLowerCase();
    return (
      /^\/ticket(\/|$)/.test(p) ||
      /^\/recibo(\/|$)/.test(p) ||
      /^\/imprimir_pago(\/|$)/.test(p) ||
      /^\/imprimir_cierre(\/|$)/.test(p) ||
      /^\/admin\/imprimir_cierre(\/|$)/.test(p) ||
      /^\/admin\/imprimir_cierre_fecha(\/|$)/.test(p) ||
      /^\/admin\/banco_cajeros\/recibo_entrega(\/|$)/.test(p) ||
      /^\/admin\/banco_cajeros\/recibo_entrega_58mm(\/|$)/.test(p)
    );
  }

  function ensureTicketThermalCssFresh() {
    if (!document || !document.head) return;
    var id = "ticket-thermal-css-fresh";
    var old = document.getElementById(id);
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = "/static/ticket_thermal.css?v=20260620-ticket&t=" + Date.now();
    document.head.appendChild(link);
  }

  function detectUiPage(pathname) {
    var p = String(pathname || "/");
    if (p === "/") return "login";
    if (p === "/crear_usuario" || p.indexOf("/crear_usuario") === 0) return "crear-usuario";
    if (p.indexOf("/venta") === 0) return "venta";
    if (p.indexOf("/ganadores") === 0 || p.indexOf("/actualizar_resultados") === 0) return "resultados";
    if (p.indexOf("/admin") === 0) return "dashboard";
    return "app";
  }

  function setModernUiFlags() {
    if (!document || !document.body) return;
    var page = typeof window.__detectUiPage === "function"
      ? window.__detectUiPage(window.location && window.location.pathname)
      : detectUiPage(window.location && window.location.pathname);
    document.documentElement.classList.add("ui-modern", "page-" + page);
    document.documentElement.setAttribute("data-ui-page", page);
    document.body.classList.add("ui-modern", "page-" + page);
    document.body.setAttribute("data-ui-page", page);
  }

  function formatMoney(value) {
    var n = Number(value || 0);
    try {
      return n.toLocaleString("es-DO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } catch (_e) {
      return n.toFixed(2);
    }
  }

  function readMoneyFromText(text) {
    var t = String(text || "");
    var m = t.match(/-?\d[\d,]*(?:\.\d{1,2})?/);
    if (!m) return null;
    var clean = m[0].replace(/,/g, "");
    var num = Number(clean);
    return isNaN(num) ? null : num;
  }

  var __adminKpiFetchState = { lastFetchMs: 0, inFlight: false };

  function requestAdminKpisSnapshot(force) {
    if (!isAdminHomePath(window.location && window.location.pathname)) return;
    var now = Date.now();
    if (!force && (now - (__adminKpiFetchState.lastFetchMs || 0) < 45000)) return;
    if (__adminKpiFetchState.inFlight) return;
    __adminKpiFetchState.inFlight = true;
    fetch("/api/admin/dashboard_kpis", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok && d.kpis) {
          try { window.__adminKpisLatest = d.kpis; } catch (_e) {}
        }
      })
      .catch(function () {})
      .finally(function () {
        __adminKpiFetchState.inFlight = false;
        __adminKpiFetchState.lastFetchMs = Date.now();
        try {
          if (typeof window.__refreshModernTopbarStats === "function") window.__refreshModernTopbarStats();
          refreshDashboardHeroFromKpis();
        } catch (_e) {}
      });
  }

  function ticketsHoyFromKpi() {
    try {
      var k = window.__adminKpisLatest || {};
      var v = Number(k.tickets_hoy);
      if (isFinite(v) && v >= 0) return Math.round(v);
    } catch (_e) {}
    var dom = document.getElementById("adm-kpi-tickets-hoy");
    if (dom) {
      var t = parseInt((dom.textContent || "").trim(), 10);
      if (isFinite(t) && t >= 0) return t;
    }
    return null;
  }

  function ventasHoyFromKpi() {
    try {
      var k = window.__adminKpisLatest || {};
      var v = Number(
        k.banco_ventas_hoy != null ? k.banco_ventas_hoy :
        k.total_ventas != null ? k.total_ventas :
        k.ventas_dia
      );
      if (isFinite(v) && v >= 0) return v;
    } catch (_e) {}
    return readMoneyFromText(readValueText(["#adm-kpi-banco-ventas", "#adm-kpi-vc-main", "#adm-kpi-vd-main"], "RD$ --"));
  }

  function insightRowsFromKpi(key, mapFn, domFallback) {
    try {
      var k = window.__adminKpisLatest || {};
      var rows = k[key];
      if (rows && rows.length) {
        var out = [];
        for (var i = 0; i < rows.length; i++) out.push(mapFn(rows[i]));
        return out;
      }
    } catch (_e) {}
    return domFallback || [];
  }

  function refreshDashboardHeroFromKpis() {
    if (!isAdminHomePath(window.location && window.location.pathname)) return;
    var ventasEl = document.getElementById("dashKpiVentas");
    if (ventasEl) {
      var vh = ventasHoyFromKpi();
      ventasEl.textContent = vh !== null && vh !== undefined ? "RD$ " + formatMoney(vh) : readValueText(["#adm-kpi-vd-main", "#adm-kpi-banco-ventas"], "RD$ --");
    }
    var tkEl = document.getElementById("dashKpiTickets");
    if (tkEl) {
      var tk = ticketsHoyFromKpi();
      tkEl.textContent = tk !== null ? String(tk) : "--";
    }
    fillAdminInsights();
  }
  window.refreshDashboardHeroFromKpis = refreshDashboardHeroFromKpis;

  function sessionWelcomeName() {
    if (window.__SESSION_USER_DISPLAY__) {
      var globalName = String(window.__SESSION_USER_DISPLAY__ || "").trim();
      if (globalName) return globalName;
    }
    var welcomeMeta = document.querySelector('meta[name="session-welcome"]');
    var welcomeRaw = welcomeMeta && (welcomeMeta.getAttribute("content") || "").trim();
    if (welcomeRaw && /^Bienvenido,\s*/i.test(welcomeRaw)) {
      return welcomeRaw.replace(/^Bienvenido,\s*/i, "").trim();
    }
    var sessionEl = document.getElementById("sessionUserDisplay");
    if (sessionEl) {
      var fromSpan = (sessionEl.textContent || "").trim();
      if (fromSpan && /^Bienvenido,\s*/i.test(fromSpan)) {
        return fromSpan.replace(/^Bienvenido,\s*/i, "").trim();
      }
      var fromData = (sessionEl.getAttribute("data-username") || "").trim();
      if (fromData) return fromData.toUpperCase();
    }
    var metaFull = document.querySelector('meta[name="session-display-name"]');
    var full = metaFull && (metaFull.getAttribute("content") || "").trim();
    if (full) return full;
    var metaUser = document.querySelector('meta[name="session-username"]');
    var user = metaUser && (metaUser.getAttribute("content") || "").trim();
    if (user) return user.toUpperCase();
    var tokens = [
      "[data-username]",
      ".sb-user-name",
      ".user-name",
      ".sidebar [data-user-name]"
    ];
    for (var i = 0; i < tokens.length; i++) {
      var el = document.querySelector(tokens[i]);
      var txt = el && (el.textContent || "").trim();
      if (txt && txt.toLowerCase() !== "usuario activo") return String(txt).toUpperCase();
    }
    return "";
  }

  function sessionRole() {
    if (window.__SESSION_ROLE__) {
      return String(window.__SESSION_ROLE__ || "").trim().toLowerCase();
    }
    var meta = document.querySelector('meta[name="session-role"]');
    return meta ? String(meta.getAttribute("content") || "").trim().toLowerCase() : "";
  }

  function isCajeroStaffRole() {
    var role = sessionRole();
    if (role === "admin" || role === "super_admin") return false;
    return role === "cajero" || role === "user" || role === "supervisor" || role === "collector";
  }

  function cajeroSidebarAllowedHref(href) {
    var raw = String(href || "").trim().toLowerCase();
    if (!raw || raw === "/logout") return true;
    var path = raw.split("?")[0];
    if (path === "/venta" || path === "/reporte" || path === "/ganadores") return true;
    if (path === "/mis_pagos_cajero" || path === "/imprimir_cierre") return true;
    if (path.indexOf("/admin/resumen_loteria") === 0) return true;
    if (path.indexOf("/admin/pagos") === 0 && path.indexOf("/admin/pagos_cajero") !== 0) return true;
    if (path.indexOf("/ticket/") === 0 || path.indexOf("/pagar/") === 0 || path.indexOf("/imprimir_pago") === 0) return true;
    return false;
  }

  function pruneSidebarForCajero(sidebar) {
    if (!sidebar) return;
    var links = sidebar.querySelectorAll(".sb-link");
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      var href = a.getAttribute("href") || "";
      if (href === "/logout") continue;
      if (!cajeroSidebarAllowedHref(href)) a.remove();
    }
    sidebar.querySelectorAll(".sb-link--virtual").forEach(function (node) {
      node.remove();
    });
    sidebar.querySelectorAll(".sb-group-title").forEach(function (node) {
      node.remove();
    });
    sidebar.querySelectorAll(".sb-section").forEach(function (sec) {
      if (!sec.querySelector(".sb-link")) sec.remove();
    });
    document.body.classList.add("role-cajero");
  }

  function sessionWelcomeText() {
    if (window.__SESSION_WELCOME__) {
      var globalWelcome = String(window.__SESSION_WELCOME__ || "").trim();
      if (globalWelcome) return globalWelcome;
    }
    var welcomeMeta = document.querySelector('meta[name="session-welcome"]');
    var welcomeRaw = welcomeMeta && (welcomeMeta.getAttribute("content") || "").trim();
    if (welcomeRaw) return welcomeRaw;
    var sessionEl = document.getElementById("sessionUserDisplay");
    if (sessionEl) {
      var fromSpan = (sessionEl.textContent || "").trim();
      if (fromSpan) return fromSpan;
    }
    var name = sessionWelcomeName();
    return name ? ("Bienvenido, " + name) : "";
  }

  function applyAuthenticatedWelcomeUi() {
    var welcome = sessionWelcomeText();
    var name = sessionWelcomeName();
    if (!welcome && !name) return;
    var title = document.getElementById("dashHeroTitle");
    if (title) title.textContent = welcome || ("Bienvenido, " + name);
    document.querySelectorAll("[data-auth-welcome]").forEach(function (node) {
      if (node.id === "sessionUserDisplay") return;
      node.textContent = welcome || ("Bienvenido, " + name);
    });
    var userStat = document.querySelector('.topbar-stat[data-kind="user"]');
    if (userStat) {
      var lbl = userStat.querySelector(".topbar-stat__label");
      var val = userStat.querySelector(".topbar-stat__value");
      if (lbl) lbl.textContent = "Bienvenido";
      if (val) val.textContent = name || welcome.replace(/^Bienvenido,\s*/i, "").trim();
    }
    var ventaUser = document.getElementById("ventaHeadUser");
    if (ventaUser) {
      var ventaWelcome = window.__SESSION_WELCOME_VENTA__
        ? String(window.__SESSION_WELCOME_VENTA__ || "").trim()
        : "";
      if (!ventaWelcome && window.__SESSION_USER_DISPLAY_VENTA__) {
        var rawVenta = String(window.__SESSION_USER_DISPLAY_VENTA__ || "").trim();
        if (rawVenta) ventaWelcome = "Bienvenido, " + rawVenta;
      }
      if (ventaWelcome) ventaUser.textContent = "👤 " + ventaWelcome;
    }
  }

  window.sessionWelcomeName = sessionWelcomeName;
  window.sessionWelcomeText = sessionWelcomeText;
  window.applyAuthenticatedWelcomeUi = applyAuthenticatedWelcomeUi;

  function sidebarUsernameFallback() {
    return sessionWelcomeName() || "Usuario";
  }

  function ensureSidebarCloseButton() {
    var head = document.querySelector(".sidebar .sb-head");
    if (!head || head.querySelector(".sb-close-btn")) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "sb-close-btn";
    btn.setAttribute("aria-label", "Cerrar menu");
    btn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    btn.addEventListener("click", function () {
      if (typeof window.closeSideMenu === "function") window.closeSideMenu();
      else {
        var sb = document.getElementById("sidebar");
        var bd = document.getElementById("sb-backdrop");
        if (sb) sb.classList.remove("open");
        if (bd) bd.classList.remove("open");
      }
    });
    head.appendChild(btn);
  }

  function ensureTopbarStats() {
    var topbar = document.querySelector(".topbar");
    if (!topbar) return;
    var stats = document.getElementById("topbarStats");
    if (!stats) {
      stats = document.createElement("div");
      stats.id = "topbarStats";
      stats.className = "topbar-stats";
      stats.innerHTML = ""
        + '<div class="topbar-stat" data-kind="balance"><i class="fa-solid fa-wallet"></i><span class="topbar-stat__label">Balance</span><b class="topbar-stat__value">--</b></div>'
        + '<div class="topbar-stat" data-kind="tickets"><i class="fa-solid fa-ticket"></i><span class="topbar-stat__label">Tickets Hoy</span><b class="topbar-stat__value">0</b></div>'
        + '<div class="topbar-stat" data-kind="clock"><i class="fa-regular fa-clock"></i><span class="topbar-stat__label">Fecha y hora</span><b class="topbar-stat__value">--</b></div>'
        + '<div class="topbar-stat" data-kind="noti"><i class="fa-regular fa-bell"></i><span class="topbar-stat__label">Notificaciones</span><b class="topbar-stat__value">En vivo</b></div>'
        + '<div class="topbar-stat" data-kind="user"><i class="fa-regular fa-user"></i><span class="topbar-stat__label">Bienvenido</span><b class="topbar-stat__value"></b></div>';
      topbar.appendChild(stats);
    }

    if (typeof window.__applyMobileLayout === "function") {
      window.__applyMobileLayout();
    }

    function setValue(kind, value) {
      var row = stats.querySelector('.topbar-stat[data-kind="' + kind + '"] .topbar-stat__value');
      if (row) row.textContent = value;
    }

    function computeBalanceText() {
      var selectors = [
        "#adm-kpi-banco-gen",
        ".ventas-hoy__val",
        ".ventas-hoy",
        ".venta-cart-total span"
      ];
      for (var i = 0; i < selectors.length; i++) {
        var el = document.querySelector(selectors[i]);
        if (!el) continue;
        var val = readMoneyFromText(el.textContent);
        if (val !== null) return "RD$ " + formatMoney(val);
      }
      return "RD$ --";
    }

    function formatNowText() {
      try {
        var n = new Date();
        var fecha = n.toLocaleDateString("es-DO", { year: "numeric", month: "2-digit", day: "2-digit" });
        var hora = n.toLocaleTimeString("es-DO", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true });
        return fecha + " " + hora;
      } catch (_e) {
        return "--";
      }
    }

    function computeTicketsText() {
      var kpiTickets = ticketsHoyFromKpi();
      if (kpiTickets !== null) return String(kpiTickets);
      if (isAdminHomePath(window.location && window.location.pathname)) {
        requestAdminKpisSnapshot(false);
      }
      var rows = document.querySelectorAll("#ventaJugadasBody tr.venta-cart-row");
      if (rows && rows.length) return String(rows.length);
      var cards = document.querySelectorAll("#ventaCartList .venta-cart-item");
      if (cards && cards.length) return String(cards.length);
      var adminRows = document.querySelectorAll(".dashboard table tbody tr");
      if (adminRows && adminRows.length) return String(adminRows.length);
      return "0";
    }

    function computeNotiText() {
      var p = readMoneyFromText(readValueText(["#adm-kpi-ph-main", "#adm-kpi-pt-main"], "0"));
      if (p !== null && p > 0) return "Pendientes";
      return "En vivo";
    }

    function refreshStats() {
      setValue("balance", computeBalanceText());
      setValue("tickets", computeTicketsText());
      setValue("clock", formatNowText());
      setValue("noti", computeNotiText());
      applyAuthenticatedWelcomeUi();
      ensureTopbarBranding();
    }

    refreshStats();
    window.__refreshModernTopbarStats = refreshStats;

    var bodyRows = document.getElementById("ventaJugadasBody");
    if (bodyRows && !bodyRows.__modernObserverBound) {
      bodyRows.__modernObserverBound = true;
      var observer = new MutationObserver(refreshStats);
      observer.observe(bodyRows, { childList: true, subtree: false });
    }
    setInterval(refreshStats, 1000);
    setTimeout(refreshStats, 1200);
  }

  function ensureTopbarBranding() {
    var brand = document.querySelector(".brand-badge");
    if (!brand) return;
    var noisy = brand.querySelectorAll(".brand-badge__title, .brand-badge__sub");
    for (var i = 0; i < noisy.length; i++) noisy[i].remove();
    var txt = brand.querySelector(".brand-badge__text");
    if (!txt) {
      txt = document.createElement("span");
      txt.className = "brand-badge__text";
      brand.appendChild(txt);
    }
    txt.textContent = "LA QUE NO FALLA";
    brand.setAttribute("aria-label", "LA QUE NO FALLA");
  }

  function sidebarMenuMeta(href) {
    var h = String(href || "").toLowerCase();
    var list = [
      { m: ["/admin"], e: true, g: "dashboard", gt: "Dashboard", go: 1, l: "Dashboard", o: 1, ic: "fa-solid fa-house" },

      { m: ["/venta"], g: "ventas", gt: "Ventas", go: 2, l: "Venta", o: 1, ic: "fa-solid fa-ticket" },
      { m: ["/admin/jugadas?reimpresion=1"], e: true, g: "ventas", gt: "Ventas", go: 2, l: "Reimpresion", o: 3, ic: "fa-solid fa-print" },
      { m: ["/admin/jugadas"], g: "ventas", gt: "Ventas", go: 2, l: "Tickets", o: 2, ic: "fa-solid fa-receipt" },
      { m: ["/ticket/", "/imprimir"], g: "ventas", gt: "Ventas", go: 2, l: "Reimpresion", o: 3, ic: "fa-solid fa-print" },

      { m: ["/reporte/finanzas/dashboard"], g: "reportes", gt: "Reportes", go: 3, l: "Dashboard Financiero", o: 1, ic: "fa-solid fa-chart-line" },
      { m: ["/reporte/ganancias/mensual?legacy=1", "/reporte/ganancias/mensual"], g: "reportes", gt: "Reportes", go: 3, l: "Legacy Ganancia/Perdida", o: 2, ic: "fa-solid fa-chart-area" },
      { m: ["/reporte"], g: "reportes", gt: "Reportes", go: 3, l: "Reporte General", o: 3, ic: "fa-solid fa-chart-column" },

      { m: ["/ganadores"], g: "riesgo", gt: "Ganadores y Riesgo", go: 4, l: "Ganadores", o: 0, ic: "fa-solid fa-trophy" },
      { m: ["/admin/limites/global?tab=calientes"], e: true, g: "riesgo", gt: "Ganadores y Riesgo", go: 4, l: "Numeros Calientes", o: 1, ic: "fa-solid fa-fire" },
      { m: ["/admin/limites/global?tab=tendencia"], e: true, g: "riesgo", gt: "Ganadores y Riesgo", go: 4, l: "Tendencia", o: 3, ic: "fa-solid fa-arrow-trend-up" },
      { m: ["/admin/limites/global?tab=frios"], e: true, g: "riesgo", gt: "Ganadores y Riesgo", go: 4, l: "Numeros Frios", o: 4, ic: "fa-solid fa-snowflake" },
      { m: ["/admin/limites/global?tab=riesgo"], e: true, g: "riesgo", gt: "Ganadores y Riesgo", go: 4, l: "Riesgo por Loteria", o: 5, ic: "fa-solid fa-triangle-exclamation" },
      { m: ["/admin/limites/global?tab=bloqueados", "/admin/limites?tab=bloqueados"], e: true, g: "riesgo", gt: "Ganadores y Riesgo", go: 4, l: "Bloqueados", o: 6, ic: "fa-solid fa-ban" },

      { m: ["/admin/resumen_loteria"], g: "control", gt: "Control", go: 5, l: "Resumen Loteria", o: 1, ic: "fa-solid fa-table-list" },
      { m: ["/admin/pagos"], g: "control", gt: "Control", go: 5, l: "Historial Pagos", o: 2, ic: "fa-solid fa-money-bill-wave" },
      { m: ["/admin/ranking"], g: "control", gt: "Control", go: 5, l: "Ranking Cajeros", o: 3, ic: "fa-solid fa-ranking-star" },

      { m: ["/admin/banco"], g: "banco", gt: "Banco", go: 6, l: "Banco General", o: 1, ic: "fa-solid fa-building-columns" },
      { m: ["/admin/banco_cajeros"], g: "banco", gt: "Banco", go: 6, l: "Movimientos", o: 2, ic: "fa-solid fa-arrow-right-arrow-left" },
      { m: ["/admin/balance_adjustments"], g: "banco", gt: "Banco", go: 6, l: "Ajustes", o: 3, ic: "fa-solid fa-sliders" },

      { m: ["/admin/limites?vista=loterias"], e: true, g: "limites", gt: "Limites", go: 7, l: "Limites por Loteria", o: 3, ic: "fa-solid fa-diagram-project" },
      { m: ["/admin/limites/global"], g: "limites", gt: "Limites", go: 7, l: "Limites Globales", o: 1, ic: "fa-solid fa-shield-halved" },
      { m: ["/admin/limites"], g: "limites", gt: "Limites", go: 7, l: "Limites por Numero", o: 2, ic: "fa-solid fa-hashtag" },

      { m: ["/crear_usuario", "/admin/usuarios", "/usuarios"], g: "admin", gt: "Admin", go: 8, l: "Usuarios", o: 1, ic: "fa-solid fa-users" },
      { m: ["/admin/auditoria"], g: "admin", gt: "Admin", go: 8, l: "Auditoria", o: 2, ic: "fa-solid fa-fingerprint" },
      { m: ["/admin/historial_cierres"], g: "admin", gt: "Admin", go: 8, l: "Historial de Cierres", o: 3, ic: "fa-solid fa-clock-rotate-left" },
      { m: ["/admin/cierres_financieros"], g: "admin", gt: "Admin", go: 8, l: "Snapshots Financieros", o: 4, ic: "fa-solid fa-camera-retro" },
      { m: ["/admin/imprimir_cierre"], g: "admin", gt: "Admin", go: 8, l: "Imprimir Cierre General", o: 5, ic: "fa-solid fa-print" },
      { m: ["/configuracion", "/admin/config"], g: "admin", gt: "Admin", go: 8, l: "Configuracion", o: 6, ic: "fa-solid fa-gear" }
    ];
    for (var i = 0; i < list.length; i++) {
      var item = list[i];
      var matches = false;
      for (var j = 0; j < item.m.length; j++) {
        if (item.e) {
          if (h === item.m[j]) { matches = true; break; }
        } else if (h.indexOf(item.m[j]) === 0) {
          matches = true; break;
        }
      }
      if (matches) return item;
    }
    return null;
  }

  function cleanupSidebarDuplicates(sidebar) {
    if (!sidebar) return;
    sidebar.querySelectorAll(".sb-group-title, .sb-link--virtual").forEach(function (el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
    var seen = {};
    sidebar.querySelectorAll(".sb-scroll .sb-link").forEach(function (a) {
      var href = (a.getAttribute("href") || "").split("?")[0].toLowerCase();
      if (!href || href === "/logout") return;
      if (seen[href]) {
        if (a.parentNode) a.parentNode.removeChild(a);
        return;
      }
      seen[href] = true;
      if (a.querySelector(".sb-txt")) {
        a.querySelectorAll(".sb-link-text").forEach(function (dup) {
          if (dup.parentNode) dup.parentNode.removeChild(dup);
        });
      }
    });
    sidebar.querySelectorAll(".sb-section").forEach(function (sec) {
      if (!sec.querySelector(".sb-link")) {
        if (sec.parentNode) sec.parentNode.removeChild(sec);
      }
    });
  }

  function ensureSidebarMenuOrganization() {
    var sidebar = document.querySelector(".sidebar");
    if (!sidebar) return;
    if (sidebar.getAttribute("data-cajero-menu") === "1" || isCajeroStaffRole()) {
      pruneSidebarForCajero(sidebar);
      return;
    }
    cleanupSidebarDuplicates(sidebar);
  }

  function readValueText(selectorList, fallback) {
    for (var i = 0; i < selectorList.length; i++) {
      var el = document.querySelector(selectorList[i]);
      if (!el) continue;
      var txt = (el.textContent || "").trim();
      if (txt) return txt;
    }
    return fallback || "RD$ --";
  }

  function isAdminHomePath(pathname) {
    var p = String(pathname || "").toLowerCase();
    return p === "/admin" || p === "/admin/";
  }

  function ensureDashboardWelcomeHero() {
    if (!isAdminHomePath(window.location && window.location.pathname)) return;
    var dash = document.querySelector(".dashboard");
    if (!dash) return;
    var hero = document.getElementById("modernDashboardHero");
    if (!hero) {
      hero = document.createElement("section");
      hero.id = "modernDashboardHero";
      hero.className = "dash-hero";
      hero.innerHTML = ""
        + '<h1 class="dash-hero-title" id="dashHeroTitle">Bienvenido, Usuario</h1>'
        + '<p class="dash-hero-sub">Panel financiero premium con actividad operativa en tiempo real.</p>'
        + '<div class="dash-kpis">'
        + '  <div class="dash-kpi dash-kpi--bank"><span class="dash-kpi__label">🏦 Banco General</span><span class="dash-kpi__value" id="dashKpiBalance">RD$ --</span></div>'
        + '  <div class="dash-kpi dash-kpi--ventas"><span class="dash-kpi__label">💰 Ventas Hoy</span><span class="dash-kpi__value" id="dashKpiVentas">RD$ --</span></div>'
        + '  <div class="dash-kpi dash-kpi--tickets"><span class="dash-kpi__label">🎟 Tickets Hoy</span><span class="dash-kpi__value" id="dashKpiTickets">--</span></div>'
        + '  <div class="dash-kpi dash-kpi--pend"><span class="dash-kpi__label">🏆 Premios Pendientes</span><span class="dash-kpi__value" id="dashKpiPend">RD$ --</span></div>'
        + '  <div class="dash-kpi dash-kpi--gain"><span class="dash-kpi__label">📈 Ganancia Actual</span><span class="dash-kpi__value" id="dashKpiGanancia">RD$ --</span></div>'
        + '  <div class="dash-kpi dash-kpi--risk"><span class="dash-kpi__label">⚠ Riesgo Actual</span><span class="dash-kpi__value" id="dashKpiRiesgo">RD$ --</span></div>'
        + '</div>'
        + '<div class="dash-quick">'
        + '  <a class="dash-quick__btn" href="/venta"><i class="fa-solid fa-ticket"></i> Venta</a>'
        + '  <a class="dash-quick__btn" href="/ganadores"><i class="fa-solid fa-trophy"></i> Ganadores</a>'
        + '  <a class="dash-quick__btn" href="/admin/pagos"><i class="fa-solid fa-money-bill-wave"></i> Pagos</a>'
        + '  <a class="dash-quick__btn" href="/admin/limites/global"><i class="fa-solid fa-shield-halved"></i> Limites</a>'
        + '  <a class="dash-quick__btn" href="/admin/banco"><i class="fa-solid fa-building-columns"></i> Banco</a>'
        + '</div>'
        + '<div class="admin-insights" id="adminInsightsGrid">'
        + '  <section class="admin-insight"><h3>Ventas del día</h3><ul id="insVentasDia"><li>Sin datos</li></ul></section>'
        + '  <section class="admin-insight"><h3>Top loterías</h3><ul id="insTopLoterias"><li>Sin datos</li></ul></section>'
        + '  <section class="admin-insight"><h3>Top números vendidos</h3><ul id="insTopNumeros"><li>Sin datos</li></ul></section>'
        + '  <section class="admin-insight"><h3>Top cajeros</h3><ul id="insTopCajeros"><li>Sin datos</li></ul></section>'
        + '  <section class="admin-insight"><h3>Ganadores pendientes</h3><ul id="insPendientes"><li>Sin datos</li></ul></section>'
        + '  <section class="admin-insight"><h3>Últimos tickets</h3><ul id="insUltimosTickets"><li>Sin datos</li></ul></section>'
        + '  <section class="admin-insight admin-insight--wide"><h3>Actividad reciente</h3><ul id="insActividad"><li>Sin datos</li></ul></section>'
        + '</div>';
      dash.insertBefore(hero, dash.firstChild);
    }

    var user = sessionWelcomeName();
    var title = document.getElementById("dashHeroTitle");
    if (title) title.textContent = sessionWelcomeText() || ("Bienvenido, " + (user || "Usuario"));
    applyAuthenticatedWelcomeUi();
    var map = [
      ["dashKpiBalance", ["#adm-kpi-banco-gen", "#adm-kpi-vc-balvis-wrap", "#adm-kpi-vc-main"], "RD$ --"],
      ["dashKpiVentas", ["#adm-kpi-banco-ventas", "#adm-kpi-vc-main", "#adm-kpi-vd-main"], "RD$ --"],
      ["dashKpiPend", ["#adm-kpi-ph-main", "#adm-kpi-pt-main"], "RD$ 0.00"],
      ["dashKpiGanancia", ["#adm-kpi-vd-n", "#adm-kpi-vc-balvis", "#adm-kpi-brk-tot"], "RD$ 0.00"],
      ["dashKpiRiesgo", ["#adm-kpi-banco-premios", "#adm-kpi-vd-p"], "RD$ 0.00"]
    ];
    for (var i = 0; i < map.length; i++) {
      var target = document.getElementById(map[i][0]);
      if (target) target.textContent = readValueText(map[i][1], map[i][2]);
    }
    var tk = document.getElementById("dashKpiTickets");
    var tkKpi = ticketsHoyFromKpi();
    if (tk) tk.textContent = tkKpi !== null ? String(tkKpi) : "--";
    var ventasEl = document.getElementById("dashKpiVentas");
    if (ventasEl) {
      var vh = ventasHoyFromKpi();
      if (vh !== null && vh !== undefined) ventasEl.textContent = "RD$ " + formatMoney(vh);
    }
    requestAdminKpisSnapshot(false);
    fillAdminInsights();
    enhanceDashboardHeroVisuals();
  }

  function setInsightList(id, items) {
    var el = document.getElementById(id);
    if (!el) return;
    if (!items || !items.length) {
      el.innerHTML = "<li>Sin datos</li>";
      return;
    }
    el.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var li = document.createElement("li");
      li.textContent = items[i];
      el.appendChild(li);
    }
  }

  function parseTopFromTableByHeader(headerNeedle, maxItems) {
    var tables = document.querySelectorAll(".dashboard table");
    for (var i = 0; i < tables.length; i++) {
      var t = tables[i];
      var ths = t.querySelectorAll("thead th, tr:first-child th");
      var targetIdx = -1;
      for (var j = 0; j < ths.length; j++) {
        if (normalizeLotteryName(ths[j].textContent || "").indexOf(headerNeedle) !== -1) {
          targetIdx = j;
          break;
        }
      }
      if (targetIdx < 0) continue;
      var out = [];
      var rows = t.querySelectorAll("tbody tr");
      for (var r = 0; r < rows.length && out.length < (maxItems || 5); r++) {
        var c = rows[r].children;
        if (!c || c.length <= targetIdx) continue;
        var txt = (c[targetIdx].textContent || "").trim();
        if (!txt) continue;
        out.push(txt);
      }
      if (out.length) return out;
    }
    return [];
  }

  function fillAdminInsights() {
    if (!isAdminHomePath(window.location && window.location.pathname)) return;
    setInsightList("insVentasDia", [
      "Ventas: " + readValueText(["#adm-kpi-banco-ventas", "#adm-kpi-vd-main", "#adm-kpi-vc-main"], "RD$ --"),
      "Premios: " + readValueText(["#adm-kpi-vd-p", "#adm-kpi-vc-prem"], "RD$ --"),
      "Entregas: " + readValueText(["#adm-kpi-vd-e", "#adm-kpi-vc-ent"], "RD$ --")
    ]);
    setInsightList("insTopLoterias", insightRowsFromKpi("top_loterias", function (r) {
      return String(r.lottery || "—") + " · RD$ " + formatMoney(r.total);
    }, parseTopFromTableByHeader("loter", 5)));
    setInsightList("insTopNumeros", insightRowsFromKpi("top_numeros", function (r) {
      var lot = r.lottery ? " (" + r.lottery + ")" : "";
      return String(r.numero || "—") + lot + " · RD$ " + formatMoney(r.total);
    }, parseTopFromTableByHeader("numero", 5)));
    setInsightList("insTopCajeros", insightRowsFromKpi("top_cajeros", function (r) {
      return String(r.cajero || "—") + " · RD$ " + formatMoney(r.ventas != null ? r.ventas : r.total);
    }, parseTopFromTableByHeader("cajero", 5)));
    setInsightList("insPendientes", [
      "Hoy: " + readValueText(["#adm-kpi-ph-main"], "RD$ 0.00"),
      "Total: " + readValueText(["#adm-kpi-pt-main"], "RD$ 0.00")
    ]);
    var ultimos = [];
    try {
      var uk = window.__adminKpisLatest || {};
      var rows = uk.ultimos_tickets;
      if (rows && rows.length) {
        for (var u = 0; u < rows.length; u++) {
          var t = rows[u];
          var hora = t.hora ? " · " + t.hora : "";
          ultimos.push("#" + t.id + hora + " · " + String(t.cajero || "—") + " · RD$ " + formatMoney(t.monto));
        }
      }
    } catch (_e2) {}
    setInsightList("insUltimosTickets", ultimos.length ? ultimos : parseTopFromTableByHeader("ticket", 6));
    setInsightList("insActividad", [
      "Actualización: " + (new Date()).toLocaleString("es-DO"),
      "Balance general: " + readValueText(["#adm-kpi-banco-gen"], "RD$ --"),
      "Ganancia ciclo: " + readValueText(["#adm-kpi-vc-balvis-wrap"], "RD$ --")
    ]);
  }

  function enhanceDashboardHeroVisuals() {
    if (!isAdminHomePath(window.location && window.location.pathname)) return;
    var kpis = [
      ["dashKpiBalance", "dash-kpi--bank", "🏦", "Banco General"],
      ["dashKpiVentas", "dash-kpi--ventas", "💠", "Ventas Hoy"],
      ["dashKpiTickets", "dash-kpi--tickets", "🎟", "Tickets Hoy"],
      ["dashKpiPend", "dash-kpi--pend", "🏆", "Premios Pendientes"],
      ["dashKpiGanancia", "dash-kpi--gain", "📈", "Ganancia Actual"],
      ["dashKpiRiesgo", "dash-kpi--risk", "⚠️", "Riesgo Actual"]
    ];
    for (var i = 0; i < kpis.length; i++) {
      var valueNode = document.getElementById(kpis[i][0]);
      if (!valueNode) continue;
      var card = valueNode.closest(".dash-kpi");
      if (!card) continue;
      card.classList.add(kpis[i][1]);
      var label = card.querySelector(".dash-kpi__label");
      if (label) {
        label.innerHTML = '<span class="dash-kpi__icon">' + kpis[i][2] + '</span><span class="dash-kpi__labeltxt">' + kpis[i][3] + "</span>";
      }
    }

    var insights = [
      ["insVentasDia", "admin-insight--ventas", "💰", "Ventas del día"],
      ["insTopLoterias", "admin-insight--loterias", "🎰", "Top loterías"],
      ["insTopNumeros", "admin-insight--numeros", "🔢", "Top números vendidos"],
      ["insTopCajeros", "admin-insight--cajeros", "👑", "Top cajeros"],
      ["insPendientes", "admin-insight--pendientes", "🏆", "Ganadores pendientes"],
      ["insUltimosTickets", "admin-insight--tickets", "🎫", "Últimos tickets"],
      ["insActividad", "admin-insight--actividad", "📡", "Actividad reciente"]
    ];
    for (var j = 0; j < insights.length; j++) {
      var ul = document.getElementById(insights[j][0]);
      if (!ul) continue;
      var section = ul.closest(".admin-insight");
      if (!section) continue;
      section.classList.add(insights[j][1]);
      var h3 = section.querySelector("h3");
      if (h3) h3.innerHTML = '<span class="admin-insight__icon">' + insights[j][2] + '</span><span>' + insights[j][3] + "</span>";
    }
  }

  function markTopbarPresence() {
    if (!document || !document.body) return;
    var hasTopbar = !!document.querySelector(".topbar");
    document.body.classList.toggle("no-topbar", !hasTopbar);
  }

  function normalizeLotteryName(name) {
    var src = String(name || "").trim();
    if (!src) return "";
    var s = src.toLowerCase();
    try {
      s = s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    } catch (_e) {}
    s = s.replace(/\s+/g, " ").trim();
    return s;
  }

  function lotteryAssetKey(name) {
    var s = normalizeLotteryName(name);
    var map = [
      ["anguila", "anguila"],
      ["florida", "florida"],
      ["loteria real", "real"],
      ["real", "real"],
      ["la primera", "la_primera"],
      ["lotedom", "lotedom"],
      ["loteka", "loteka"],
      ["leidsa", "leidsa"],
      ["loteria nacional", "nacional"],
      ["nacional", "nacional"],
      ["new york", "new_york"],
      ["king lottery", "king_lottery"],
      ["la suerte", "la_suerte"],
      ["georgia", "georgia"],
      ["quiniela real", "real"]
    ];
    for (var i = 0; i < map.length; i++) {
      if (s.indexOf(map[i][0]) !== -1) return map[i][1];
    }
    return "";
  }

  function obtener_logo_loteria(nombre) {
    var key = lotteryAssetKey(nombre);
    if (!key) return [];
    var candidates = [
      "/static/img/loterias/" + key + ".png",
      "/static/img/loterias/" + key.replace(/_/g, "-") + ".png",
      "/static/img/loterias/" + key.replace(/-/g, "_") + ".png"
    ];
    var out = [];
    for (var i = 0; i < candidates.length; i++) {
      if (out.indexOf(candidates[i]) === -1) out.push(candidates[i]);
    }
    return out;
  }
  window.obtener_logo_loteria = obtener_logo_loteria;

  function lotteryInitials(name) {
    var tokens = String(name || "")
      .replace(/[^a-zA-Z0-9\u00C0-\u017F ]/g, " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!tokens.length) return "LT";
    if (tokens.length === 1) return tokens[0].slice(0, 2).toUpperCase();
    return (tokens[0][0] + tokens[1][0]).toUpperCase();
  }

  function lotteryVisualConfig(name) {
    var s = normalizeLotteryName(name);
    var cfg = { key: "default", label: lotteryInitials(name), title: name || "Loteria" };
    if (s.indexOf("anguila") !== -1) return { key: "anguila", label: "ANG", title: "Anguila" };
    if (s.indexOf("florida") !== -1) return { key: "florida", label: "FL", title: "Florida" };
    if (s.indexOf("king lottery") !== -1) return { key: "king_lottery", label: "👑 KL", title: "King Lottery" };
    if (s.indexOf("la primera") !== -1) return { key: "la_primera", label: "1RA", title: "La Primera" };
    if (s.indexOf("lotedom") !== -1) return { key: "lotedom", label: "LOT", title: "Lotedom" };
    if (s.indexOf("loteka") !== -1) return { key: "loteka", label: "TEKA", title: "Loteka" };
    if (s.indexOf("leidsa") !== -1) return { key: "leidsa", label: "L", title: "Leidsa" };
    if (s.indexOf("new york") !== -1) return { key: "new_york", label: "NY", title: "New York" };
    if (s.indexOf("nacional") !== -1) return { key: "nacional", label: "NAC", title: "Nacional" };
    if (s.indexOf("la suerte") !== -1) return { key: "la_suerte", label: "LS", title: "La Suerte" };
    if (s.indexOf("georgia") !== -1) return { key: "georgia", label: "GA", title: "Georgia" };
    if (s.indexOf("real") !== -1) return { key: "real", label: "REAL", title: "Loteria Real" };
    return cfg;
  }

  function buildLotteryVisual(name, extraClass) {
    var lotName = String(name || "").trim() || "Loteria";
    var cfg = lotteryVisualConfig(lotName);
    var wrap = document.createElement("span");
    wrap.className = "lottery-visual " + (extraClass || "");
    wrap.classList.add("lottery-theme-" + cfg.key);
    wrap.setAttribute("data-lottery-key", cfg.key);
    wrap.title = cfg.title;
    wrap.setAttribute("aria-hidden", "true");

    var avatar = document.createElement("span");
    avatar.className = "lottery-avatar";
    avatar.textContent = cfg.label;
    wrap.appendChild(avatar);

    var paths = obtener_logo_loteria(lotName);
    if (paths.length) {
      var img = document.createElement("img");
      img.className = "lottery-logo";
      img.alt = "";
      img.loading = "lazy";
      img.decoding = "async";
      var idx = 0;
      function loadNext() {
        if (idx >= paths.length) {
          img.remove();
          return;
        }
        img.src = paths[idx++];
      }
      img.addEventListener("load", function () {
        wrap.classList.add("has-logo");
      });
      img.addEventListener("error", function () {
        loadNext();
      });
      loadNext();
      wrap.appendChild(img);
    }
    return wrap;
  }

  function dedupeMetaRankingCards() {
    var track = document.getElementById("metasPanelTrack");
    if (!track) return;
    if (track.classList.contains("ranking-track--live") || track.dataset.marqueeLoop === "1") return;
    var cards = track.querySelectorAll(".meta-card");
    if (!cards.length) return;
    var seen = {};
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var nameEl = card.querySelector(".meta-card__name");
      var key = normalizeLotteryName((nameEl && nameEl.textContent) || card.textContent || "");
      if (!key) continue;
      if (seen[key]) {
        card.remove();
      } else {
        seen[key] = true;
      }
    }
  }

  function initMetaRankingVisualCleanup() {
    var track = document.getElementById("metasPanelTrack");
    if (!track || track.dataset.visualCleanObserver === "1") return;
    track.dataset.visualCleanObserver = "1";
    /* Ranking cajeros: el marquee duplica tarjetas a propósito — no deduplicar. */
  }

  function splitLotteryAndDraw(labelText) {
    var raw = String(labelText || "").trim();
    if (!raw) return { lottery: "", draw: "" };
    var parts = raw.split(" — ");
    if (parts.length <= 1) return { lottery: raw, draw: "" };
    return {
      lottery: parts[0].trim(),
      draw: parts.slice(1).join(" — ").trim()
    };
  }

  function parseDrawHour(raw) {
    var s = String(raw || "").trim().toUpperCase();
    var m = s.match(/(\d{1,2})\s*:\s*(\d{2})\s*(AM|PM)?/);
    if (!m) return null;
    var h = parseInt(m[1], 10);
    if (m[3] === "PM" && h < 12) h += 12;
    if (m[3] === "AM" && h === 12) h = 0;
    return h;
  }

  function drawPeriodMeta(drawText) {
    var raw = String(drawText || "").trim();
    var norm = normalizeLotteryName(raw);
    if (norm.indexOf("manana") !== -1) return { code: "MAÑANA", emoji: "🌅", key: "manana" };
    if (norm.indexOf("mediodia") !== -1 || norm.indexOf("medio dia") !== -1) return { code: "MEDIODÍA", emoji: "☀️", key: "mediodia" };
    if (norm.indexOf("tarde") !== -1) return { code: "TARDE", emoji: "🌇", key: "tarde" };
    if (norm.indexOf("noche") !== -1) return { code: "NOCHE", emoji: "🌙", key: "noche" };
    var h = parseDrawHour(raw);
    if (h === null) return { code: "TARDE", emoji: "🌇", key: "tarde" };
    if (h < 12) return { code: "MAÑANA", emoji: "🌅", key: "manana" };
    if (h === 12) return { code: "MEDIODÍA", emoji: "☀️", key: "mediodia" };
    if (h < 18) return { code: "TARDE", emoji: "🌇", key: "tarde" };
    return { code: "NOCHE", emoji: "🌙", key: "noche" };
  }

  function createVentaDrawBadge(drawText) {
    var meta = drawPeriodMeta(drawText);
    var badge = document.createElement("span");
    badge.className = "venta-draw-badge venta-draw-badge--" + meta.key;
    badge.textContent = meta.emoji + " " + meta.code;
    return badge;
  }

  function decorateVentaSearchArea() {
    var form = document.querySelector('form[action="/admin/buscar_ticket"]');
    if (!form) return;
    if (!form.classList.contains("venta-ticket-search")) {
      form.classList.add("venta-ticket-search");
    }
    var parent = form.parentElement;
    if (parent && !parent.classList.contains("venta-ticket-search-wrap")) {
      parent.classList.add("venta-ticket-search-wrap");
    }
  }

  function decorateVentaLotteryCatalog() {
    var catalog = document.getElementById("ventaLotCatalog");
    if (!catalog) return;
    var names = catalog.querySelectorAll(".venta-lot-item .venta-lot-name");
    for (var i = 0; i < names.length; i++) {
      var nameEl = names[i];
      if (nameEl.dataset.lotteryDecorated === "1") continue;
      var parts = splitLotteryAndDraw(nameEl.textContent);
      nameEl.textContent = "";
      nameEl.classList.add("venta-lot-name--enhanced");
      nameEl.appendChild(buildLotteryVisual(parts.lottery, "lottery-visual--venta"));
      var txtWrap = document.createElement("span");
      txtWrap.className = "venta-lot-name-text";
      var lotTxt = document.createElement("span");
      lotTxt.className = "venta-lot-name-main";
      lotTxt.textContent = parts.lottery || "Loteria";
      txtWrap.appendChild(lotTxt);
      nameEl.appendChild(txtWrap);
      nameEl.dataset.lotteryDecorated = "1";
    }
  }

  function observeVentaCatalog() {
    var catalog = document.getElementById("ventaLotCatalog");
    if (!catalog || catalog.dataset.observingModernUi === "1") return;
    catalog.dataset.observingModernUi = "1";
    var observer = new MutationObserver(function () {
      decorateVentaLotteryCatalog();
    });
    observer.observe(catalog, { childList: true, subtree: true });
    decorateVentaLotteryCatalog();
  }

  function decorateResultadosLotteryCells() {
    var rows = document.querySelectorAll(".gnr-section-results .tabla-resultados-main tbody tr");
    if (!rows.length) return;
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var lotTd = row.querySelector("td.res-lot-col");
      if (!lotTd || lotTd.dataset.lotteryDecorated === "1") continue;
      var lotName = (lotTd.getAttribute("data-lottery") || lotTd.textContent || "").trim();
      var logoTd = row.querySelector("td.res-logo-col");
      if (logoTd && logoTd.dataset.lotteryDecorated !== "1") {
        logoTd.textContent = "";
        var logoBox = document.createElement("div");
        logoBox.className = "res-logo-wrap";
        logoBox.appendChild(buildLotteryVisual(lotName, "lottery-visual--result"));
        logoTd.appendChild(logoBox);
        logoTd.dataset.lotteryDecorated = "1";
      }

      lotTd.textContent = "";
      var box = document.createElement("div");
      box.className = "res-lot-wrap";
      if (!logoTd) {
        box.appendChild(buildLotteryVisual(lotName, "lottery-visual--result"));
      }
      var txt = document.createElement("span");
      txt.className = "res-lot-name";
      txt.textContent = lotName || "Loteria";
      box.appendChild(txt);
      lotTd.appendChild(box);
      lotTd.dataset.lotteryDecorated = "1";
    }
  }

  function decorateGenericLotteryColumns() {
    var tables = document.querySelectorAll("table");
    for (var ti = 0; ti < tables.length; ti++) {
      var table = tables[ti];
      var heads = table.querySelectorAll("thead th, tr:first-child th");
      var lotIdx = -1;
      for (var hi = 0; hi < heads.length; hi++) {
        var hTxt = normalizeLotteryName(heads[hi].textContent || "");
        if (hTxt.indexOf("loteria") !== -1 || hTxt.indexOf("lottery") !== -1 || hTxt.indexOf("sorteo") !== -1) {
          lotIdx = hi;
          break;
        }
      }
      if (lotIdx < 0) continue;
      var rows = table.querySelectorAll("tbody tr");
      for (var ri = 0; ri < rows.length; ri++) {
        var cells = rows[ri].children;
        if (!cells || cells.length <= lotIdx) continue;
        var td = cells[lotIdx];
        if (!td || td.dataset.genericLotteryDecorated === "1") continue;
        if (td.classList && (td.classList.contains("res-lot-col") || td.classList.contains("res-logo-col"))) {
          td.dataset.genericLotteryDecorated = "1";
          continue;
        }
        if (td.querySelector(".lottery-visual")) {
          td.dataset.genericLotteryDecorated = "1";
          continue;
        }
        var rawName = String(td.getAttribute("data-lottery") || td.textContent || "").trim();
        if (!rawName || rawName.length > 60) continue;
        if (!/[a-zA-Z\u00C0-\u017F]/.test(rawName)) continue;
        var wrap = document.createElement("div");
        wrap.className = "res-lot-wrap";
        wrap.appendChild(buildLotteryVisual(rawName, "lottery-visual--generic"));
        var txt = document.createElement("span");
        txt.className = "res-lot-name";
        txt.textContent = rawName;
        wrap.appendChild(txt);
        td.textContent = "";
        td.appendChild(wrap);
        td.dataset.genericLotteryDecorated = "1";
      }
    }
  }

  function observeLotteryDecorations() {
    if (!document || !document.body) return;
    if (document.body.dataset.lotteryDecorObserver === "1") return;
    document.body.dataset.lotteryDecorObserver = "1";
    var timer = null;
    var observer = new MutationObserver(function () {
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () {
        decorateVentaLotteryCatalog();
        decorateResultadosLotteryCells();
        decorateGenericLotteryColumns();
      }, 60);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function enhanceActionButtons() {
    var map = [
      ["guardar", "fa-solid fa-floppy-disk"],
      ["editar", "fa-solid fa-pen-to-square"],
      ["eliminar", "fa-solid fa-trash"],
      ["bloquear", "fa-solid fa-lock"],
      ["desbloquear", "fa-solid fa-lock-open"],
      ["actualizar", "fa-solid fa-rotate"],
      ["imprimir", "fa-solid fa-print"]
    ];
    var nodes = document.querySelectorAll("button, .btn, .admin-btn, a.admin-btn");
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (!el || el.dataset.iconEnhanced === "1") continue;
      if (el.querySelector("i")) {
        el.dataset.iconEnhanced = "1";
        continue;
      }
      var txt = normalizeLotteryName(el.textContent || "");
      var iconCls = "";
      for (var j = 0; j < map.length; j++) {
        if (txt.indexOf(map[j][0]) !== -1) {
          iconCls = map[j][1];
          break;
        }
      }
      if (!iconCls) continue;
      var ico = document.createElement("i");
      ico.className = iconCls;
      ico.style.marginRight = "7px";
      el.insertBefore(ico, el.firstChild);
      el.dataset.iconEnhanced = "1";
    }
  }

  function cleanAdminBtnLabel(text) {
    var t = String(text || "").replace(/\s+/g, " ").trim();
    t = t.replace(/^[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+/, "").trim();
    return t || "Accion";
  }

  function adminActionMeta(el) {
    var href = String((el && el.getAttribute && el.getAttribute("href")) || "").toLowerCase();
    var txt = normalizeLotteryName((el && el.textContent) || "");
    var rules = [
      { when: function () { return href.indexOf("/admin/limites") === 0 || txt.indexOf("control limites") !== -1; }, cls: "admin-action--limites", icon: "fa-solid fa-shield-halved" },
      { when: function () { return href === "/crear_usuario" || txt.indexOf("crear usuario") !== -1; }, cls: "admin-action--crear-usuario", icon: "fa-solid fa-user-plus" },
      { when: function () { return href === "/usuarios_pendientes" || txt.indexOf("aprobar usuarios") !== -1; }, cls: "admin-action--aprobar-usuarios", icon: "fa-solid fa-user-check" },
      { when: function () { return href.indexOf("/superadmin/control-usuarios") === 0 || txt.indexOf("control usuarios") !== -1; }, cls: "admin-action--control-usuarios", icon: "fa-solid fa-users-gear" },
      { when: function () { return href.indexOf("/admin/balance_adjustments") === 0 || txt.indexOf("historial ajustes") !== -1; }, cls: "admin-action--historial-ajustes", icon: "fa-solid fa-scale-balanced" },
      { when: function () { return href.indexOf("/admin/cajeros_balance_negativo") === 0 || txt.indexOf("balance negativo") !== -1; }, cls: "admin-action--cajeros-negativo", icon: "fa-solid fa-triangle-exclamation" },
      { when: function () { return href.indexOf("/admin/metas") === 0 || txt.indexOf("metas cajeros") !== -1; }, cls: "admin-action--metas-cajeros", icon: "fa-solid fa-bullseye" },
      { when: function () { return href.indexOf("/ventas_cajeros") === 0 || txt.indexOf("ventas por cajero") !== -1; }, cls: "admin-action--ventas-cajero", icon: "fa-solid fa-chart-bar" },
      { when: function () { return href.indexOf("/admin/imprimir_cierre") === 0 || txt.indexOf("imprimir cierre") !== -1; }, cls: "admin-action--imprimir-cierre", icon: "fa-solid fa-print" },
      { when: function () { return href.indexOf("/reporte_hoy") === 0 || txt.indexOf("ventas del dia") !== -1; }, cls: "admin-action--ventas-dia", icon: "fa-solid fa-calendar-day" },
      { when: function () { return href.indexOf("/reporte_semanal") === 0 || txt.indexOf("ventas semanales") !== -1; }, cls: "admin-action--ventas-semana", icon: "fa-solid fa-calendar-week" },
      { when: function () { return href.indexOf("/reporte_mensual") === 0 || txt.indexOf("ventas mensuales") !== -1; }, cls: "admin-action--ventas-mes", icon: "fa-solid fa-calendar-days" },
      { when: function () { return href.indexOf("/numeros_populares") === 0 || txt.indexOf("numeros mas jugados") !== -1; }, cls: "admin-action--numeros-jugados", icon: "fa-solid fa-hashtag" },
      { when: function () { return href.indexOf("/admin/pagos") === 0 || txt.indexOf("historial pagos") !== -1; }, cls: "admin-action--historial-pagos", icon: "fa-solid fa-money-bill-wave" },
      { when: function () { return href.indexOf("/admin/tickets_eliminados") === 0 || txt.indexOf("tickets eliminados") !== -1; }, cls: "admin-action--tickets-eliminados", icon: "fa-solid fa-trash-can" },
      { when: function () { return href === "/admin/banco" || txt.indexOf("banco general") !== -1; }, cls: "admin-action--banco-general", icon: "fa-solid fa-building-columns" },
      { when: function () { return href.indexOf("/admin/banco_cajeros") === 0 || txt.indexOf("banco cajeros") !== -1; }, cls: "admin-action--banco-legacy", icon: "fa-solid fa-building-user" },
      { when: function () { return href.indexOf("/admin/historial_cierres") === 0 || txt.indexOf("historial de cierres") !== -1; }, cls: "admin-action--historial-cierres", icon: "fa-solid fa-clock-rotate-left" },
      { when: function () { return href.indexOf("/admin/cierres_financieros") === 0 || txt.indexOf("snapshots financieros") !== -1; }, cls: "admin-action--snapshots", icon: "fa-solid fa-camera-retro" },
      { when: function () { return href.indexOf("/reporte/finanzas/dashboard") === 0 || txt.indexOf("dashboard financiero") !== -1; }, cls: "admin-action--dashboard-financiero", icon: "fa-solid fa-chart-line" },
      { when: function () { return href.indexOf("/reporte/ganancias/mensual") === 0 || txt.indexOf("legacy ganancia") !== -1; }, cls: "admin-action--legacy-ganancia", icon: "fa-solid fa-chart-column" },
      { when: function () { return txt.indexOf("panel de jugadas") !== -1; }, cls: "admin-action--panel-jugadas", icon: "fa-solid fa-dice" },
      { when: function () { return txt.indexOf("cerrar caja") !== -1; }, cls: "admin-action--cerrar-caja", icon: "fa-solid fa-lock" }
    ];
    for (var i = 0; i < rules.length; i++) {
      if (rules[i].when()) return rules[i];
    }
    return { cls: "admin-action--default", icon: "fa-solid fa-bolt" };
  }

  function enhanceAdminDashboardButtons() {
    if (!isAdminHomePath(window.location && window.location.pathname)) return;
    var panel = document.querySelector(".dashboard .panel");
    if (!panel) return;
    panel.classList.add("admin-actions-grid");
    var buttons = panel.querySelectorAll(".admin-btn");
    for (var i = 0; i < buttons.length; i++) {
      var el = buttons[i];
      if (!el || el.dataset.adminCardReady === "1") continue;
      var meta = adminActionMeta(el);
      var label = cleanAdminBtnLabel(el.textContent || "");
      el.classList.add("admin-action-card", meta.cls);
      el.style.width = "100%";
      el.textContent = "";
      var iconWrap = document.createElement("span");
      iconWrap.className = "admin-action-icon";
      var icon = document.createElement("i");
      icon.className = meta.icon;
      iconWrap.appendChild(icon);
      var labelWrap = document.createElement("span");
      labelWrap.className = "admin-action-label";
      labelWrap.textContent = label;
      el.appendChild(iconWrap);
      el.appendChild(labelWrap);
      el.dataset.adminCardReady = "1";
    }
  }

  function enhanceAdminFinancialCards() {
    if (!isAdminHomePath(window.location && window.location.pathname)) return;
    var scope = document.querySelector(".dashboard");
    if (!scope) return;
    var cards = scope.querySelectorAll(".card");
    var map = [
      { cls: "card-ciclo", icon: "fa-solid fa-arrows-rotate", test: function (c) { return !!c.querySelector("#adm-kpi-vc-main"); } },
      { cls: "card-ventas", icon: "fa-solid fa-sack-dollar", test: function (c) { return !!c.querySelector("#adm-kpi-vd-main"); } },
      { cls: "card-premios", icon: "fa-solid fa-triangle-exclamation", test: function (c) { return !!c.querySelector("#adm-kpi-ph-main"); } },
      { cls: "card-pendiente", icon: "fa-solid fa-hourglass-half", test: function (c) { return !!c.querySelector("#adm-kpi-pt-main"); } },
      { cls: "card-evaluacion", icon: "fa-solid fa-wave-square", test: function (c) { return !!c.querySelector("#admin-lineas-gan"); } },
      { cls: "card-ganadores", icon: "fa-solid fa-trophy", test: function (c) {
        var h3 = c.querySelector("h3");
        return !!h3 && normalizeLotteryName(h3.textContent || "").indexOf("ganadores pendientes") !== -1;
      } }
    ];
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      if (!card || card.classList.contains("admin-kpi--hidden")) continue;
      var matched = null;
      for (var m = 0; m < map.length; m++) {
        if (map[m].test(card)) {
          matched = map[m];
          break;
        }
      }
      if (!matched) continue;
      card.classList.add("admin-fin-card", matched.cls);
      var h = card.querySelector("h3");
      if (h) h.classList.add("admin-fin-card__title");
      var metric = card.querySelector(".metric");
      if (metric) metric.classList.add("admin-fin-card__metric");
      if (!card.querySelector(".admin-fin-card__icon")) {
        var icon = document.createElement("span");
        icon.className = "admin-fin-card__icon";
        icon.innerHTML = '<i class="' + matched.icon + '"></i>';
        card.insertBefore(icon, card.firstChild);
      }
    }
  }

  function isTableEnhanceable(table) {
    if (!table || table.dataset.tableEnhanced === "1") return false;
    if (table.classList.contains("nc-mini-table")) return false;
    if (table.closest(".lim-card")) return false;
    var rows = table.querySelectorAll("tbody tr");
    if (!rows || rows.length < 8) return false;
    return true;
  }

  function renderEnhancedTableState(state) {
    var q = (state.searchInput.value || "").trim().toLowerCase();
    var size = parseInt(state.pageSize.value || "10", 10) || 10;
    var filtered = [];
    for (var i = 0; i < state.rows.length; i++) {
      var r = state.rows[i];
      var txt = (r.textContent || "").toLowerCase();
      if (!q || txt.indexOf(q) !== -1) filtered.push(r);
      r.style.display = "none";
    }
    var pages = Math.max(1, Math.ceil(filtered.length / size));
    if (state.page > pages) state.page = pages;
    var ini = (state.page - 1) * size;
    var end = Math.min(filtered.length, ini + size);
    for (var k = ini; k < end; k++) filtered[k].style.display = "";
    state.info.textContent = "Pagina " + state.page + " / " + pages + " · " + filtered.length + " filas";
    state.prev.disabled = state.page <= 1;
    state.next.disabled = state.page >= pages;
  }

  function enhanceDataTables() {
    var tables = document.querySelectorAll("table");
    for (var i = 0; i < tables.length; i++) {
      var table = tables[i];
      if (!isTableEnhanceable(table)) continue;
      table.dataset.tableEnhanced = "1";
      table.classList.add("modern-table-enhanced");
      var wrap = document.createElement("div");
      wrap.className = "modern-table-wrap";
      var controls = document.createElement("div");
      controls.className = "modern-table-tools";
      controls.innerHTML = ""
        + '<input type="search" class="modern-table-search" placeholder="Buscar en tabla...">'
        + '<select class="modern-table-size"><option value="10">10</option><option value="20">20</option><option value="50">50</option></select>'
        + '<button type="button" class="modern-table-nav prev">←</button>'
        + '<span class="modern-table-info">Pagina 1 / 1</span>'
        + '<button type="button" class="modern-table-nav next">→</button>';
      var parent = table.parentNode;
      parent.insertBefore(wrap, table);
      wrap.appendChild(controls);
      wrap.appendChild(table);
      var state = {
        rows: Array.prototype.slice.call(table.querySelectorAll("tbody tr")),
        searchInput: controls.querySelector(".modern-table-search"),
        pageSize: controls.querySelector(".modern-table-size"),
        prev: controls.querySelector(".modern-table-nav.prev"),
        next: controls.querySelector(".modern-table-nav.next"),
        info: controls.querySelector(".modern-table-info"),
        page: 1
      };
      if (!state.rows.length) continue;
      state.searchInput.addEventListener("input", function (s) {
        return function () {
          s.page = 1;
          renderEnhancedTableState(s);
        };
      }(state));
      state.pageSize.addEventListener("change", function (s) {
        return function () {
          s.page = 1;
          renderEnhancedTableState(s);
        };
      }(state));
      state.prev.addEventListener("click", function (s) {
        return function () {
          if (s.page <= 1) return;
          s.page -= 1;
          renderEnhancedTableState(s);
        };
      }(state));
      state.next.addEventListener("click", function (s) {
        return function () {
          s.page += 1;
          renderEnhancedTableState(s);
        };
      }(state));
      renderEnhancedTableState(state);
    }
  }

  function initUiContrastEnhancements() {
    if (!document || !document.body) return;
    var page = document.body.getAttribute("data-ui-page") || "";
    if (page === "venta") {
      decorateVentaSearchArea();
      observeVentaCatalog();
      decorateVentaLotteryCatalog();
    }
    if (page === "resultados") {
      decorateResultadosLotteryCells();
    }
    decorateGenericLotteryColumns();
    observeLotteryDecorations();
    initMetaRankingVisualCleanup();
    ensureDashboardWelcomeHero();
    applyAuthenticatedWelcomeUi();
    enhanceActionButtons();
    enhanceAdminDashboardButtons();
    enhanceAdminFinancialCards();
    enhanceDataTables();
  }

  function initClassicLimitesAssist() {
    var p = String((window.location && window.location.pathname) || "");
    if (p !== "/admin/limites") return;
    if (!document || !document.body) return;
    document.body.classList.add("page-limites-classic");

    var card = document.querySelector(".card");
    if (!card || card.dataset.limitesAssistReady === "1") return;
    card.dataset.limitesAssistReady = "1";

    var grid = card.querySelector(".grid-numeros");
    if (grid) {
      grid.style.display = "none";
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "limites-grid-toggle";
      toggle.textContent = "Mostrar números 00-99";
      toggle.addEventListener("click", function () {
        var isHidden = grid.style.display === "none";
        grid.style.display = isHidden ? "grid" : "none";
        toggle.textContent = isHidden ? "Ocultar números 00-99" : "Mostrar números 00-99";
      });
      grid.parentNode.insertBefore(toggle, grid);
    }

    var globalLink = card.querySelector('a[href="/admin/limites/global"]');
    if (globalLink) {
      var note = document.createElement("div");
      note.className = "limites-classic-note";
      note.innerHTML = "Usa la versión simplificada del control de límites.";
      var cta = document.createElement("a");
      cta.href = "/admin/limites/global";
      cta.className = "limites-classic-cta";
      cta.textContent = "Abrir control simplificado";
      note.appendChild(cta);
      card.insertBefore(note, card.firstChild.nextSibling);
    }
  }

  function initModernUi() {
    var path = (window.location && window.location.pathname) || "";
    if (isTicketOrPrintPath(path)) {
      removeDuplicateThemeLinks();
      ensureTicketThermalCssFresh();
      return;
    }
    setModernUiFlags();
    injectModernThemeCss();
    markTopbarPresence();
    ensureTopbarBranding();
    ensureSidebarCloseButton();
    ensureSidebarMenuOrganization();
    ensureTopbarStats();
    initUiContrastEnhancements();
    initClassicLimitesAssist();
    setTimeout(function () {
      ensureDashboardWelcomeHero();
      applyAuthenticatedWelcomeUi();
      enhanceActionButtons();
      enhanceAdminDashboardButtons();
      enhanceAdminFinancialCards();
      enhanceDataTables();
      if (typeof window.__restartRankingTicker === "function") {
        window.__restartRankingTicker();
      }
    }, 350);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initModernUi);
  } else {
    setTimeout(initModernUi, 0);
  }
})();
