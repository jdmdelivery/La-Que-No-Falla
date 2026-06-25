(function () {
  var dashboardLoaded = false;
  var lastDashboardRefresh = 0;
  var REFRESH_COOLDOWN_MS = 60000;
  var SSR_FULL = typeof window !== "undefined" && window.__ADMIN_SSR_KPI__;

  function fmtRD(n) {
    return "RD$ " + Number(n || 0).toFixed(2);
  }
  function setTxt(id, v, rd) {
    var e = document.getElementById(id);
    if (!e) return;
    e.textContent = rd ? fmtRD(v) : Number(v || 0).toFixed(2);
  }
  function paintMetricBig(id, val) {
    var e = document.getElementById(id);
    if (!e) return;
    e.textContent = fmtRD(val);
    var p = e.parentElement;
    if (p && p.style) {
      var n = Number(val) || 0;
      if (id === "adm-kpi-vc-main" || id === "adm-kpi-vd-main")
        p.style.color = n > 0 ? "#16a34a" : "#1e293b";
      else if (id === "adm-kpi-hist-main") p.style.color = n < 0 ? "#dc2626" : "#1e40af";
      else if (id === "adm-kpi-qa-bal") p.style.color = n < 0 ? "#dc2626" : "#15803d";
      else if (id === "adm-kpi-qp-bal") p.style.color = n < 0 ? "#dc2626" : "#a16207";
      else if (id === "adm-kpi-ph-main") p.style.color = n > 0 ? "#ea580c" : "#1e293b";
      else if (id === "adm-kpi-pt-main") p.style.color = n > 0 ? "#dc2626" : "#1e293b";
    }
    var card = e.closest(".metric-card");
    if (card && card.style) {
      var nz = Math.abs(Number(val) || 0) > 0.009;
      if (id === "adm-kpi-vc-main" || id === "adm-kpi-vd-main")
        card.style.background = nz ? "#dcfce7" : "white";
      else if (id === "adm-kpi-ph-main") card.style.background = nz ? "#ffedd5" : "white";
      else if (id === "adm-kpi-pt-main") card.style.background = nz ? "#fee2e2" : "white";
    }
  }
  function hydrate(k) {
    k = k || {};
    try {
      var ciclo = Number(
        k.banco_ventas_hoy != null ? k.banco_ventas_hoy :
        k.total_ventas != null ? k.total_ventas :
        k.ventas_dia || 0
      );
      var prem = Number(
        k.ventas_dia_premios != null ? k.ventas_dia_premios : k.total_premios || 0
      );
      var ent = Number(
        k.ventas_dia_entregas != null ? k.ventas_dia_entregas :
        (k._entregado_adm != null ? k._entregado_adm : k.entregado_ciclo_admin || 0)
      );
      k.ventas_dia = ciclo;
      k.ventas_dia_neto = Number(ciclo - prem - ent);
      k.tickets_hoy = Math.round(Number(k.tickets_hoy || 0));
    } catch (_sync) {}
    try {
      window.__adminKpisLatest = k;
    } catch (_e) {}
    paintMetricBig("adm-kpi-vc-main", k.total_ventas);
    setTxt("adm-kpi-vc-prem", k.total_premios, false);
    var ent = k._entregado_adm;
    if (ent == null) ent = k.entregado_ciclo_admin;
    setTxt("adm-kpi-vc-ent", ent, false);
    var bv = Number(
      k.balance_final_ajustado != null ? k.balance_final_ajustado : k.balance_real_visual || 0
    );
    var elb = document.getElementById("adm-kpi-vc-balvis");
    if (elb) elb.textContent = Number(bv).toFixed(2);
    var wr = document.getElementById("adm-kpi-vc-balvis-wrap");
    if (wr) wr.style.color = bv < -0.005 ? "#dc2626" : "#16a34a";

    setTxt("adm-kpi-brk-v", k.total_ventas, false);
    setTxt("adm-kpi-brk-p", k.total_premios, false);
    var entB = k._entregado_adm;
    if (entB == null || entB === undefined) entB = k.entregado_ciclo_admin;
    setTxt("adm-kpi-brk-e", entB, false);
    setTxt("adm-kpi-brk-a", k.sum_ajustes_balance, false);
    var brkt = document.getElementById("adm-kpi-brk-tot");
    if (brkt) brkt.textContent = Number(bv).toFixed(2);
    var brkw = document.getElementById("adm-kpi-brk-tot-wrap");
    if (brkw) brkw.style.color = bv < -0.005 ? "#dc2626" : "#16a34a";

    paintMetricBig("adm-kpi-hist-main", k.hist_balance);
    setTxt("adm-kpi-hist-v", k.hist_ventas, false);
    setTxt("adm-kpi-hist-p", k.hist_premios, false);
    setTxt("adm-kpi-hist-e", k.hist_entregado, false);
    setTxt("adm-kpi-hist-a", k.hist_ajustes, false);

    var qa = k.quincena_actual || {};
    var qp = k.quincena_pasada || {};
    paintMetricBig("adm-kpi-qa-bal", qa.balance);
    setTxt("adm-kpi-qa-v", qa.ventas, false);
    setTxt("adm-kpi-qa-p", qa.premios, false);
    setTxt("adm-kpi-qa-e", qa.entregado, false);
    paintMetricBig("adm-kpi-qp-bal", qp.balance);
    setTxt("adm-kpi-qp-v", qp.ventas, false);
    setTxt("adm-kpi-qp-p", qp.premios, false);
    setTxt("adm-kpi-qp-e", qp.entregado, false);

    paintMetricBig("adm-kpi-vd-main", k.ventas_dia);
    setTxt("adm-kpi-vd-p", k.ventas_dia_premios, false);
    setTxt("adm-kpi-vd-e", k.ventas_dia_entregas, false);
    var vn = document.getElementById("adm-kpi-vd-n");
    if (vn) {
      var nx = Number(k.ventas_dia_neto || 0);
      vn.textContent = Number(nx).toFixed(2);
      vn.parentElement.style.color = nx < -0.005 ? "#dc2626" : "#16a34a";
    }
    var tkDom = document.getElementById("adm-kpi-tickets-hoy");
    if (tkDom) tkDom.textContent = String(k.tickets_hoy || 0);

    paintMetricBig("adm-kpi-ph-main", k.pendiente_hoy);
    paintMetricBig("adm-kpi-pt-main", k.pendiente_total);

    paintMetricBig("adm-kpi-banco-gen", k.banco_balance_general);
    var bancoCaj = document.getElementById("adm-kpi-banco-caj");
    if (bancoCaj) bancoCaj.textContent = fmtRD(k.banco_dinero_en_cajeros || k.banco_dinero_cajeros);
    var bancoVen = document.getElementById("adm-kpi-banco-ventas");
    if (bancoVen) bancoVen.textContent = fmtRD(k.banco_ventas_hoy);
    var bancoPrem = document.getElementById("adm-kpi-banco-premios");
    if (bancoPrem) bancoPrem.textContent = fmtRD(k.banco_premios_hoy);

    var m = document.getElementById("ajusteMontoAuto");
    var sug = Number(k.monto_auto_ajuste_balance || 0).toFixed(2);
    if (m) {
      m.dataset.montoSugerido = sug;
      var cur = String(m.value || "").replace(",", ".");
      if (cur === "0.00" || cur === "0" || Number(cur) === 0) m.value = sug;
    }

    var wrap = document.getElementById("adm-wrap-ajuste-balance");
    if (wrap) wrap.style.display = k.puede_mostrar_btn_ajuste ? "block" : "none";
  }

  function hint(elId, on) {
    var el = document.getElementById(elId);
    if (!el) return;
    el.style.display = on ? "inline" : "none";
  }

  function runInitial() {
    var lm = document.getElementById("admin-kpis-lazy-msg");
    fetch("/api/admin/dashboard_kpis", { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        if (!d || !d.ok || !d.kpis) {
          if (lm)
            lm.textContent =
              "No se pudo cargar el resumen financiero. Recarga la página.";
          return;
        }
        hydrate(d.kpis);
        if (typeof window.refreshDashboardHeroFromKpis === "function") window.refreshDashboardHeroFromKpis();
        dashboardLoaded = true;
        lastDashboardRefresh = Date.now();
        if (lm) lm.textContent = "Resumen financiero actualizado.";
      })
      .catch(function () {
        if (lm) lm.textContent = "Error de red al cargar el resumen financiero.";
      });
  }

  function silentKpiRefresh() {
    if (!dashboardLoaded) return;
    if (Date.now() - lastDashboardRefresh < REFRESH_COOLDOWN_MS) return;
    hint("admin-dashboard-refresh-hint", true);
    fetch("/api/admin/dashboard_kpis", { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        hint("admin-dashboard-refresh-hint", false);
        if (!d || !d.ok || !d.kpis) return;
        hydrate(d.kpis);
        if (typeof window.refreshDashboardHeroFromKpis === "function") window.refreshDashboardHeroFromKpis();
        lastDashboardRefresh = Date.now();
      })
      .catch(function () {
        hint("admin-dashboard-refresh-hint", false);
      });
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) return;
    silentKpiRefresh();
  });

  if (SSR_FULL) {
    if (window.__ADMIN_KPI_SSR__) {
      hydrate(window.__ADMIN_KPI_SSR__);
      if (typeof window.refreshDashboardHeroFromKpis === "function") {
        window.refreshDashboardHeroFromKpis();
      }
    }
    dashboardLoaded = true;
    lastDashboardRefresh = Date.now();
    setTimeout(runInitial, 300);
    setInterval(silentKpiRefresh, 120000);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", runInitial);
  } else {
    runInitial();
  }

  try {
    window.__adminDashboardLazy = {
      dashboardLoaded: function () {
        return dashboardLoaded;
      },
      lastRefresh: function () {
        return lastDashboardRefresh;
      },
      refreshNow: silentKpiRefresh,
      hydrate: hydrate,
    };
  } catch (e) {}
})();
