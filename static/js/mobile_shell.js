/**
 * Mobile shell — drawer navigation, page classes, ranking visibility.
 */
(function (w, d) {
  var MQ = "(max-width: 768px)";

  function detectPage(pathname) {
    var p = String(pathname || "/");
    if (p === "/" || p === "/login" || p.indexOf("/login") === 0) return "login";
    if (p === "/crear_usuario" || p.indexOf("/crear_usuario") === 0) return "crear-usuario";
    if (p.indexOf("/venta") === 0 || p.indexOf("/ticket") === 0) return "venta";
    if (p.indexOf("/ganadores") === 0 || p.indexOf("/actualizar_resultados") === 0) return "ganadores";
    if (p.indexOf("/reporte") === 0) return "reporte";
    if (p.indexOf("/mis_pagos_cajero") === 0) return "historial-pagos";
    if (p.indexOf("/admin/resumen_loteria") === 0 || p.indexOf("/resumen_loteria") === 0) return "resumen";
    if (p === "/admin" || p.indexOf("/admin/limites") === 0) return "dashboard";
    if (p.indexOf("/admin") === 0) return "dashboard";
    return "app";
  }

  function rankingPages(page) {
    return page === "venta" || page === "dashboard";
  }

  function applyPageShellClasses() {
    var page = detectPage(w.location && w.location.pathname);
    var root = d.documentElement;
    var body = d.body;
    if (!body) return page;

    var pages = [
      "login",
      "crear-usuario",
      "venta",
      "ganadores",
      "resultados",
      "reporte",
      "historial-pagos",
      "resumen",
      "dashboard",
      "app",
    ];
    pages.forEach(function (cls) {
      root.classList.remove("page-" + cls);
      body.classList.remove("page-" + cls);
    });

    root.classList.add("page-" + page);
    body.classList.add("page-" + page);
    if (page === "ganadores") {
      root.classList.add("page-resultados");
      body.classList.add("page-resultados");
    }

    body.classList.toggle("shell-with-ranking", rankingPages(page));
    body.classList.toggle("shell-no-ranking", !rankingPages(page));
    root.setAttribute("data-ui-page", page);
    body.setAttribute("data-ui-page", page);
    return page;
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
      if (!w.matchMedia(MQ).matches) return;
      var a = ev.target.closest("a.sb-link, a[href]");
      if (!a || !sb.contains(a)) return;
      var href = (a.getAttribute("href") || "").trim();
      if (!href || href === "#" || href.indexOf("javascript:") === 0) return;
      closeDrawer();
      scrollTop();
    });

    d.querySelectorAll(".sb-link").forEach(function (a) {
      a.addEventListener("click", function () {
        if (!w.matchMedia(MQ).matches) return;
        closeDrawer();
        scrollTop();
      });
    });
  }

  function hideRankingIfNeeded() {
    if (!w.matchMedia(MQ).matches) return;
    var panel = d.getElementById("metasPanel");
    if (!panel) return;
    var page = d.body.getAttribute("data-ui-page") || detectPage(w.location.pathname);
    if (!rankingPages(page)) {
      panel.setAttribute("hidden", "hidden");
      panel.setAttribute("aria-hidden", "true");
    } else {
      panel.removeAttribute("hidden");
      panel.setAttribute("aria-hidden", "false");
    }
  }

  function init() {
    applyPageShellClasses();
    hideRankingIfNeeded();
    setupDrawerNav();
    closeDrawer();
  }

  w.__applyMobilePageShell = applyPageShellClasses;
  w.__closeMobileDrawer = closeDrawer;

  if (d.readyState === "loading") {
    d.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window, document);
