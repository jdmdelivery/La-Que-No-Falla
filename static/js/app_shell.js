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
    if (p.indexOf("/ganadores") === 0 || p.indexOf("/actualizar_resultados") === 0) return "resultados";
    if (p.indexOf("/admin/limites") === 0) return "dashboard";
    if (p.indexOf("/admin") === 0) return "dashboard";
    return "app";
  }

  var page = detectPage(w.location && w.location.pathname);
  var root = d.documentElement;
  root.classList.add("ui-modern", "page-" + page);
  root.setAttribute("data-ui-page", page);

  function tagBody() {
    if (!d.body) {
      w.requestAnimationFrame(tagBody);
      return;
    }
    d.body.classList.add("ui-modern", "page-" + page);
    d.body.setAttribute("data-ui-page", page);
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

  /* Teclado móvil: inputs visibles al enfocar */
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
})(
  window,
  document
);
