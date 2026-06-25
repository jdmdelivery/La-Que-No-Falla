/**
 * Shell UI — activa tema moderno antes del primer paint (evita flash legacy en F5).
 */
(function (w, d) {
  var meta = d.querySelector('meta[name="static-asset-version"]');
  w.__STATIC_ASSET_V__ = (meta && meta.content) || "20260627";

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

  function applyShellClasses(target, page) {
    if (!target) return;
    target.classList.add("ui-modern", "page-" + page, "mob-page-" + page);
    target.setAttribute("data-ui-page", page);
    if (page === "ganadores") {
      target.classList.add("page-resultados");
    }
    if (target === d.body) {
      target.classList.toggle("shell-with-ranking", page === "dashboard");
      target.classList.toggle("shell-no-ranking", page !== "dashboard");
      try {
        if (w.matchMedia("(max-width: 768px)").matches) {
          target.classList.add("mob-shell-active");
        }
      } catch (_e) {}
    }
  }

  var page = detectPage(w.location && w.location.pathname);
  var root = d.documentElement;
  applyShellClasses(root, page);

  function tagBody() {
    if (!d.body) {
      w.requestAnimationFrame(tagBody);
      return;
    }
    applyShellClasses(d.body, page);
  }
  tagBody();

  w.__detectUiPage = detectPage;
  w.__restartRankingTicker = function () {
    var track = d.getElementById("metasPanelTrack");
    if (!track || track.dataset.marqueeLoop !== "1") return;
    track.classList.remove("ranking-track--live");
    track.style.removeProperty("transform");
    track.style.removeProperty("animation");
    void track.offsetWidth;
    track.classList.add("ranking-track--live");
    track.style.animation = "moverRanking 30s linear infinite";
    var vp = d.getElementById("metasPanelViewport");
    if (vp) {
      vp.style.overflow = "hidden";
      vp.style.overflowX = "hidden";
      vp.scrollLeft = 0;
    }
  };

  function mobileInputScroll() {
    if (!w.matchMedia("(max-width: 900px)").matches) return;
    d.addEventListener(
      "focusin",
      function (ev) {
        var t = ev.target;
        if (!t || !t.matches) return;
        if (!t.matches("input, select, textarea")) return;
        setTimeout(function () {
          try {
            t.scrollIntoView({ block: "center", behavior: "smooth" });
          } catch (e) {
            try {
              t.scrollIntoView(true);
            } catch (e2) {}
          }
        }, 320);
      },
      true
    );
  }
  if (d.readyState === "loading") {
    d.addEventListener("DOMContentLoaded", mobileInputScroll);
  } else {
    mobileInputScroll();
  }
})(window, document);
