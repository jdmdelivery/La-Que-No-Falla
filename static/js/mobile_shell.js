/**
 * Mobile shell — dedicated layout controller (NOT desktop reuse).
 * Manages page classes, drawer, widget visibility, dashboard relocation.
 */
(function (w, d) {
  var MQ = "(max-width: 768px)";

  function isMobile() {
    return w.matchMedia(MQ).matches;
  }

  function detectPage(pathname) {
    var p = String(pathname || "/");
    if (p === "/" || p === "/login" || p.indexOf("/login") === 0) return "login";
    if (p === "/crear_usuario" || p.indexOf("/crear_usuario") === 0) return "crear-usuario";
    if (p.indexOf("/venta") === 0 || p.indexOf("/ticket") === 0) return "venta";
    if (p.indexOf("/ganadores") === 0 || p.indexOf("/actualizar_resultados") === 0) return "ganadores";
    if (p.indexOf("/reporte") === 0) return "reporte";
    if (p.indexOf("/mis_pagos_cajero") === 0) return "historial-pagos";
    if (p.indexOf("/admin/resumen_loteria") === 0 || p.indexOf("/resumen_loteria") === 0) return "resumen";
    if (p.indexOf("/admin/banco") === 0) return "banco";
    if (p === "/admin" || p.indexOf("/admin/limites") === 0) return "dashboard";
    if (p.indexOf("/admin") === 0) return "dashboard";
    return "app";
  }

  var MOB_PAGES = [
    "login",
    "crear-usuario",
    "venta",
    "ganadores",
    "reporte",
    "historial-pagos",
    "resumen",
    "banco",
    "dashboard",
    "app",
  ];

  function clearPageClasses(el) {
    if (!el) return;
    MOB_PAGES.forEach(function (cls) {
      el.classList.remove("page-" + cls);
      el.classList.remove("mob-page-" + cls);
      el.classList.remove("shell-with-ranking");
      el.classList.remove("shell-no-ranking");
    });
    el.classList.remove("page-resultados");
  }

  function applyPageClasses() {
    var page = detectPage(w.location && w.location.pathname);
    var root = d.documentElement;
    var body = d.body;
    if (!body) return page;

    clearPageClasses(root);
    clearPageClasses(body);

    root.classList.add("page-" + page, "mob-page-" + page);
    body.classList.add("page-" + page, "mob-page-" + page);
    root.setAttribute("data-ui-page", page);
    body.setAttribute("data-ui-page", page);

    if (page === "ganadores") {
      root.classList.add("page-resultados");
      body.classList.add("page-resultados");
    }

    if (page === "dashboard") {
      body.classList.add("shell-with-ranking");
    } else {
      body.classList.add("shell-no-ranking");
    }

    return page;
  }

  function removeFloatingVenta() {
    d.querySelectorAll("a.venta-btn").forEach(function (el) {
      el.parentNode && el.parentNode.removeChild(el);
    });
  }

  function ensureHost(parent, id, className, position) {
    if (!parent) return null;
    var host = d.getElementById(id);
    if (!host) {
      host = d.createElement("div");
      host.id = id;
      host.className = "mob-page-host " + className;
      if (position === "prepend") {
        parent.insertBefore(host, parent.firstChild);
      } else if (position === "after-metrics") {
        var metrics = parent.querySelector(".metrics");
        if (metrics && metrics.nextSibling) {
          parent.insertBefore(host, metrics.nextSibling);
        } else if (metrics) {
          metrics.parentNode.insertBefore(host, metrics.nextSibling);
        } else {
          parent.appendChild(host);
        }
      } else {
        parent.appendChild(host);
      }
    }
    return host;
  }

  function moveIntoHost(el, host) {
    if (!el || !host || host.contains(el)) return;
    host.appendChild(el);
    el.removeAttribute("hidden");
    el.setAttribute("aria-hidden", "false");
  }

  function hideEl(el) {
    if (!el) return;
    el.setAttribute("hidden", "hidden");
    el.setAttribute("aria-hidden", "true");
  }

  function relocateWidgets(page) {
    var hero = d.getElementById("brandHeroPlate");
    if (hero) hideEl(hero);

    var stats = d.getElementById("topbarStats");
    var panel = d.getElementById("metasPanel");
    var topbar = d.getElementById("appTopbar") || d.querySelector(".topbar");

    if (stats && topbar && topbar.contains(stats) && page !== "dashboard") {
      hideEl(stats);
    }

    if (page === "dashboard") {
      var dash = d.querySelector(".dashboard");
      if (dash) {
        var stripHost = ensureHost(dash, "mobDashStripHost", "mob-dash-strip-host", "prepend");
        var rankHost = ensureHost(dash, "mobDashRankingHost", "mob-dash-ranking-host", "after-metrics");
        if (stats) moveIntoHost(stats, stripHost);
        if (panel) moveIntoHost(panel, rankHost);
      }
    } else {
      hideEl(panel);
      if (stats && page !== "dashboard") hideEl(stats);
    }

    if (page === "venta") {
      hideEl(panel);
      hideEl(stats);
    }
  }

  function closeDrawer() {
    if (typeof w.closeSideMenu === "function") {
      w.closeSideMenu();
      return;
    }
    var sb = d.getElementById("sidebar");
    var bd = d.getElementById("sb-backdrop");
    if (sb) sb.classList.remove("open");
    if (bd) bd.classList.remove("open");
    d.body.classList.remove("sidebar-open");
  }

  function scrollTop() {
    try {
      w.scrollTo({ top: 0, left: 0, behavior: "smooth" });
    } catch (_e) {
      w.scrollTo(0, 0);
    }
  }

  function setupDrawerNav() {
    var sb = d.getElementById("sidebar");
    if (!sb) return;

    sb.addEventListener("click", function (ev) {
      if (!isMobile()) return;
      var a = ev.target.closest("a.sb-link, a[href]");
      if (!a || !sb.contains(a)) return;
      var href = (a.getAttribute("href") || "").trim();
      if (!href || href === "#" || href.indexOf("javascript:") === 0) return;
      closeDrawer();
      scrollTop();
    });
  }

  function applyMobileLayout() {
    if (!isMobile()) return;
    var page = applyPageClasses();
    removeFloatingVenta();
    relocateWidgets(page);
    closeDrawer();
  }

  function onResize() {
    if (isMobile()) {
      applyMobileLayout();
    }
  }

  function init() {
    applyMobileLayout();
    setupDrawerNav();

    w.addEventListener("resize", onResize);

    /* Re-run after print_ticket_app injects topbar stats */
    var tries = 0;
    var poll = setInterval(function () {
      if (!isMobile()) {
        clearInterval(poll);
        return;
      }
      tries += 1;
      relocateWidgets(detectPage(w.location.pathname));
      removeFloatingVenta();
      if (tries > 20) clearInterval(poll);
    }, 250);
  }

  w.__applyMobilePageShell = applyPageClasses;
  w.__applyMobileLayout = applyMobileLayout;
  w.__closeMobileDrawer = closeDrawer;
  w.__isMobileLayout = isMobile;

  if (d.readyState === "loading") {
    d.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window, document);
