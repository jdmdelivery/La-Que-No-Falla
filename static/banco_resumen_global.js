(function () {
  function formatRD(n) {
    return "RD$ " + Number(n || 0).toFixed(2);
  }

  async function refrescarBancoGlobal() {
    try {
      var res = await fetch("/api/banco/resumen?ts=" + Date.now(), {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!res.ok) return null;
      var body = await res.json();
      if (!body || !body.ok) return null;
      var data = body.resumen || body;

      document.querySelectorAll("[data-dinero-cajeros]").forEach(function (el) {
        el.textContent = formatRD(data.dinero_en_cajeros || 0);
      });
      document.querySelectorAll("[data-banco-general]").forEach(function (el) {
        el.textContent = formatRD(data.banco_general || 0);
      });

      return data;
    } catch (e) {
      return null;
    }
  }

  window.formatRDBanco = formatRD;
  window.refrescarBancoGlobal = refrescarBancoGlobal;

  function boot() {
    refrescarBancoGlobal();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
