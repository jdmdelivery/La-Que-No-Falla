/**
 * Mobile shell — layout controller for iPhone / Android (≤768px).
 * Page isolation, drawer, widget relocation, no global chrome bleed.
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
    if (p.indexOf("/admin") === 0) return "app";
    return "app";
  }

  var MOB_PAGES = [
    "login", "crear-usuario", "venta", "ganadores", "reporte",
    "historial-pagos", "resumen", "banco", "dashboard", "app",
  ];

  function clearPageClasses(el) {
    if (!el) return;
    MOB_PAGES.forEach(function (cls) {
      el.classList.remove("page-" + cls, "mob-page-" + cls, "shell-with-ranking", "shell-no-ranking", "mob-shell-active");
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
    if (isMobile()) {
      root.classList.add("mob-shell-active");
      body.classList.add("mob-shell-active");
    }
    root.setAttribute("data-ui-page", page);
    body.setAttribute("data-ui-page", page);

    if (page === "ganadores") {
      root.classList.add("page-resultados");
      body.classList.add("page-resultados");
    }

    body.classList.toggle("shell-with-ranking", page === "dashboard");
    body.classList.toggle("shell-no-ranking", page !== "dashboard");
    return page;
  }

  function removeFloatingVenta() {
    d.querySelectorAll("a.venta-btn").forEach(function (el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
  }

  function hideEl(el) {
    if (!el) return;
    el.setAttribute("hidden", "hidden");
    el.setAttribute("aria-hidden", "true");
  }

  function showEl(el) {
    if (!el) return;
    el.removeAttribute("hidden");
    el.setAttribute("aria-hidden", "false");
  }

  function relocateWidgets(page) {
    var hero = d.getElementById("brandHeroPlate");
    if (hero) hideEl(hero);

    var stats = d.getElementById("topbarStats");
    var panel = d.getElementById("metasPanel");
    var topbar = d.getElementById("appTopbar") || d.querySelector(".topbar");

    if (stats && topbar && topbar.contains(stats)) {
      if (page === "dashboard") {
        var strip = d.getElementById("mobDashStripHost");
        if (strip) strip.appendChild(stats);
      } else {
        hideEl(stats);
      }
    }

    if (page === "dashboard") {
      var dash = d.querySelector(".dashboard");
      var rankHost = d.getElementById("mobDashRankingHost");
      if (panel && rankHost && !rankHost.contains(panel)) {
        rankHost.appendChild(panel);
        showEl(panel);
      } else if (panel) {
        showEl(panel);
      }
    } else if (panel) {
      hideEl(panel);
      panel.style.cssText = "display:none!important;position:absolute!important;height:0!important;overflow:hidden!important;";
    }

    if (page !== "dashboard" && stats) {
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
    if (bd) {
      bd.classList.remove("open");
      bd.setAttribute("aria-hidden", "true");
    }
    d.body.classList.remove("sidebar-open");
  }

  function scrollTop() {
    try {
      w.scrollTo({ top: 0, left: 0, behavior: "instant" in w ? "instant" : "auto" });
    } catch (_e) {
      w.scrollTo(0, 0);
    }
  }

  function setupDrawerNav() {
    var sb = d.getElementById("sidebar");
    if (!sb || sb.dataset.mobNavBound === "1") return;
    sb.dataset.mobNavBound = "1";

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

  function patchToggleMenu() {
    var origClose = w.closeSideMenu;
    w.closeSideMenu = function () {
      if (typeof origClose === "function") origClose();
      else {
        var sb = d.getElementById("sidebar");
        var bd = d.getElementById("sb-backdrop");
        if (sb) sb.classList.remove("open");
        if (bd) bd.classList.remove("open");
        d.body.classList.remove("sidebar-open");
      }
    };
  }

  function applyMobileLayout() {
    if (!isMobile()) {
      d.body.classList.remove("mob-shell-active");
      return;
    }
    var page = applyPageClasses();
    removeFloatingVenta();
    relocateWidgets(page);
    setupDrawerNav();
  }

  function auditOverflow() {
    if (!isMobile()) return;
    var sw = d.documentElement.scrollWidth;
    var iw = w.innerWidth;
    var ok = sw <= iw + 1;
    console.log(
      "[MOBILE LAYOUT AUDIT] document.documentElement.scrollWidth=" + sw +
      " window.innerWidth=" + iw +
      (ok ? " OK" : " OVERFLOW — fix required")
    );
    if (!ok) {
      var offenders = [];
      d.querySelectorAll("body *").forEach(function (el) {
        if (!el.getBoundingClientRect) return;
        var r = el.getBoundingClientRect();
        if (r.width > iw + 2 || r.right > iw + 2) {
          offenders.push(el);
        }
      });
      offenders.slice(0, 8).forEach(function (el) {
        console.warn("[OVERFLOW]", el.tagName, el.className || el.id, el.getBoundingClientRect().width);
      });
    }
  }

  function init() {
    patchToggleMenu();
    applyMobileLayout();
    setupDrawerNav();
    closeDrawer();
    setTimeout(auditOverflow, 600);
    setTimeout(auditOverflow, 2000);

    w.addEventListener("resize", function () {
      applyMobileLayout();
      auditOverflow();
    });

    w.addEventListener("pageshow", function () {
      applyMobileLayout();
      scrollTop();
    });

    var obs = new MutationObserver(function () {
      if (!isMobile()) return;
      removeFloatingVenta();
      relocateWidgets(detectPage(w.location.pathname));
    });
    obs.observe(d.body, { childList: true, subtree: true });

    var tries = 0;
    var poll = setInterval(function () {
      if (!isMobile()) {
        clearInterval(poll);
        return;
      }
      tries += 1;
      relocateWidgets(detectPage(w.location.pathname));
      removeFloatingVenta();
      if (tries === 3 || tries === 12) auditOverflow();
      if (tries > 24) clearInterval(poll);
    }, 200);
  }

  w.__auditMobileOverflow = auditOverflow;

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
