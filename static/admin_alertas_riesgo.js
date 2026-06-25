(function () {
  var ROLE = String((window.__SESSION_ROLE__ || "")).toLowerCase();
  if (ROLE !== "admin" && ROLE !== "super_admin") return;

  var POLL_MS = 45000;
  var state = { items: [], loading: false, dropdownOpen: false, ready: false, knownKeys: {} };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function api(method, url, body) {
    var opts = { method: method, credentials: "same-origin", headers: {} };
    if (body != null) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (j) {
        return { ok: r.ok, j: j };
      });
    });
  }

  function resolveBancaId(item) {
    var bid = parseInt(item && item.banca_id, 10) || 0;
    if (bid > 0) return bid;
    var sel = document.getElementById("fBanca");
    if (sel && sel.value) return parseInt(sel.value, 10) || 0;
    var uid = parseInt(window.__SESSION_USER_DISPLAY__ && window.__SESSION_USER_DISPLAY__.uid, 10);
    if (!uid && window.__SESSION_USER_DISPLAY__ && typeof window.__SESSION_USER_DISPLAY__ === "object") {
      uid = parseInt(window.__SESSION_USER_DISPLAY__.id, 10) || 0;
    }
    if (ROLE === "admin" && uid > 0) return uid;
    return 0;
  }

  function cardClass(nivel) {
    var n = String(nivel || "alto").toLowerCase();
    if (n === "critico") return "ar-card ar-card--critico";
    if (n === "alto") return "ar-card ar-card--alto";
    return "ar-card";
  }

  function itemKey(it) {
    return [
      it.fecha_rd || "",
      it.banca_id || 0,
      it.lottery || "",
      it.draw || "",
      it.numero || "",
      it.origen || "",
    ].join("|");
  }

  function ensureToastWrap() {
    var wrap = document.getElementById("arToastWrap");
    if (wrap) return wrap;
    wrap = document.createElement("div");
    wrap.id = "arToastWrap";
    wrap.className = "ar-toast-wrap";
    wrap.setAttribute("aria-live", "polite");
    document.body.appendChild(wrap);
    return wrap;
  }

  function showArToast(msg, durationMs) {
    var wrap = ensureToastWrap();
    var el = document.createElement("div");
    el.className = "ar-toast ar-toast--hot";
    el.textContent = msg;
    wrap.appendChild(el);
    requestAnimationFrame(function () {
      el.classList.add("show");
    });
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 280);
    }, durationMs || 5500);
  }

  function playAlertSound() {
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      var ctx = new Ctx();
      var o = ctx.createOscillator();
      var g = ctx.createGain();
      o.type = "sine";
      o.frequency.setValueAtTime(880, ctx.currentTime);
      o.frequency.exponentialRampToValueAtTime(660, ctx.currentTime + 0.12);
      g.gain.setValueAtTime(0.0001, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.18, ctx.currentTime + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
      o.connect(g);
      g.connect(ctx.destination);
      o.start(ctx.currentTime);
      o.stop(ctx.currentTime + 0.36);
      setTimeout(function () {
        try {
          ctx.close();
        } catch (e) {}
      }, 500);
    } catch (e) {}
  }

  function pulseBell() {
    var bell = document.getElementById("arBellBtn");
    if (!bell) return;
    bell.classList.remove("ar-bell--pulse");
    void bell.offsetWidth;
    bell.classList.add("ar-bell--pulse");
    setTimeout(function () {
      bell.classList.remove("ar-bell--pulse");
    }, 1800);
  }

  function notifyNewAlertas(newItems) {
    if (!newItems || !newItems.length) return;
    playAlertSound();
    pulseBell();
    newItems.slice(0, 4).forEach(function (it) {
      var orig =
        it.origen === "historial_recalc"
          ? "Tras recalcular historial"
          : it.banca_nombre
            ? "Vivo · " + it.banca_nombre
            : "Riesgo en vivo";
      showArToast(
        "Numero " +
          (it.numero || "??") +
          " CALIENTE · " +
          (it.lottery || "") +
          " " +
          (it.draw || "") +
          " (" +
          orig +
          ")",
        6000
      );
    });
    if (newItems.length > 4) {
      showArToast("+" + (newItems.length - 4) + " numeros calientes mas. Revisa la campanita.", 5000);
    }
  }

  function renderCard(it, idx) {
    var razones = (it.razones || []).slice(0, 3).map(function (r) {
      return esc(r);
    }).join(" · ");
    var origenLbl =
      it.origen === "historial_recalc"
        ? "Historial recalculado"
        : it.banca_nombre
          ? "Vivo · " + esc(it.banca_nombre)
          : "Riesgo en vivo";
    return (
      '<div class="' +
      cardClass(it.nivel_riesgo) +
      '" data-ar-idx="' +
      idx +
      '">' +
      '<div class="ar-card__num">' +
      esc(it.numero) +
      " · " +
      esc(it.lottery) +
      " " +
      esc(it.draw) +
      "</div>" +
      '<div class="ar-card__meta">' +
      esc(it.nivel_riesgo_label || it.nivel_riesgo || "Alto") +
      " · " +
      origenLbl +
      (razones ? " · " + razones : "") +
      "</div>" +
      '<div class="ar-card__msg">' +
      esc(it.mensaje_ia || "") +
      "</div>" +
      '<div class="ar-card__acts">' +
      '<button type="button" class="ar-card__btn ar-card__btn--block" data-ar-act="block">🔒 Bloquear</button>' +
      '<button type="button" class="ar-card__btn ar-card__btn--limit" data-ar-act="limit">📉 Limitar</button>' +
      '<button type="button" class="ar-card__btn ar-card__btn--skip" data-ar-act="ignore">Ignorar hoy</button>' +
      "</div></div>"
    );
  }

  function bindCardActions(container) {
    if (!container) return;
    container.querySelectorAll("[data-ar-act]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest("[data-ar-idx]");
        if (!card) return;
        var idx = parseInt(card.getAttribute("data-ar-idx"), 10);
        var it = state.items[idx];
        if (!it) return;
        var act = btn.getAttribute("data-ar-act");
        if (act === "block") bloquear(it, btn);
        else if (act === "limit") limitar(it);
        else if (act === "ignore") ignorar(it, card);
      });
    });
  }

  function renderInto(containerId, opts) {
    opts = opts || {};
    var el = document.getElementById(containerId);
    if (!el) return;
    var listEl = el;
    if (containerId === "adminAlertasRiesgoPanel") {
      listEl = document.getElementById("adminAlertasRiesgoList");
      el.style.display = state.items.length ? "block" : "none";
    }
    if (containerId === "limitesAlertasRiesgoPanel") {
      listEl = document.getElementById("limitesAlertasRiesgoList");
      el.style.display = state.items.length ? "block" : "none";
    }
    if (!listEl) return;
    if (!state.items.length) {
      listEl.innerHTML = opts.emptyHtml || '<div class="ar-panel-empty">Sin alertas pendientes hoy (solo riesgo alto).</div>';
      return;
    }
    var max = opts.maxItems || (containerId === "arBellList" ? 8 : 12);
    var slice = state.items.slice(0, max);
    listEl.innerHTML = slice
      .map(function (it, i) {
        return renderCard(it, i);
      })
      .join("");
    bindCardActions(listEl);
  }

  function updateBadge() {
    var n = state.items.length;
    var badge = document.getElementById("arBellBadge");
    var bell = document.getElementById("arBellBtn");
    if (badge) {
      badge.textContent = n > 99 ? "99+" : String(n);
      badge.style.display = n > 0 ? "flex" : "none";
    }
    if (bell) {
      bell.setAttribute("aria-label", n + " alertas de riesgo alto");
    }
  }

  function renderAll() {
    updateBadge();
    renderInto("adminAlertasRiesgoPanel", { maxItems: 6 });
    renderInto("limitesAlertasRiesgoPanel", { maxItems: 10 });
    renderInto("arBellList", { maxItems: 8 });
  }

  function fetchAlertas(opts) {
    opts = opts || {};
    if (state.loading) return Promise.resolve();
    state.loading = true;
    var prevKeys = state.knownKeys || {};
    return api("GET", "/api/admin/alertas_riesgo")
      .then(function (x) {
        if (!(x.j && x.j.ok)) return;
        var incoming = x.j.items || [];
        var newItems = [];
        if (state.ready) {
          incoming.forEach(function (it) {
            var k = itemKey(it);
            if (!prevKeys[k]) newItems.push(it);
          });
        }
        state.items = incoming;
        var nextKeys = {};
        incoming.forEach(function (it) {
          nextKeys[itemKey(it)] = true;
        });
        state.knownKeys = nextKeys;
        renderAll();
        if (state.ready && newItems.length) {
          notifyNewAlertas(newItems);
        } else if (!state.ready) {
          state.ready = true;
        }
      })
      .catch(function () {})
      .finally(function () {
        state.loading = false;
      });
  }

  function toast(msg, ok) {
    if (typeof window.flash === "function") {
      window.flash(msg, !!ok);
      return;
    }
    if (typeof window.toast === "function") {
      window.toast(msg, !!ok, 4000);
      return;
    }
    showArToast(msg, 4000);
  }

  function bloquear(it, btn) {
    var bid = resolveBancaId(it);
    if (bid <= 0) {
      toast("Selecciona cajero/banca arriba antes de bloquear.", false);
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = "…";
    }
    api("POST", "/api/admin/limites/global", {
      accion: "numeros_calientes_bloquear_manual",
      banca_id: bid,
      lottery: it.lottery,
      draw: it.draw,
      numero: it.numero,
    })
      .then(function (x) {
        if (x.j && x.j.ok) {
          toast("✅ Número " + it.numero + " bloqueado.", true);
          if (it.notif_id) {
            api("POST", "/api/admin/alertas_riesgo/marcar_leida", { notif_id: it.notif_id });
          }
          fetchAlertas();
          if (typeof window.cargarHotDashboard === "function") window.cargarHotDashboard();
        } else {
          toast("Error: " + ((x.j && x.j.error) || "No se pudo bloquear"), false);
        }
      })
      .catch(function () {
        toast("Error de red al bloquear.", false);
      })
      .finally(function () {
        if (btn) {
          btn.disabled = false;
          btn.textContent = "🔒 Bloquear";
        }
      });
  }

  function limitar(it) {
    if (typeof window.abrirModalLimitar === "function") {
      var sel = document.getElementById("fBanca");
      if (sel && it.banca_id > 0) sel.value = String(it.banca_id);
      window.abrirModalLimitar(it.numero, it.lottery, it.draw, 0);
      return;
    }
    toast("Abre Control de límites para limitar este número.", false);
  }

  function ignorar(it, cardEl) {
    api("POST", "/api/admin/alertas_riesgo/ignorar", {
      banca_id: it.banca_id || 0,
      lottery: it.lottery,
      draw: it.draw,
      numero: it.numero,
      notif_id: it.notif_id || null,
    })
      .then(function (x) {
        if (x.j && x.j.ok) {
          if (cardEl) cardEl.remove();
          state.items = state.items.filter(function (row) {
            return itemKey(row) !== itemKey(it);
          });
          var nk = {};
          state.items.forEach(function (row) {
            nk[itemKey(row)] = true;
          });
          state.knownKeys = nk;
          renderAll();
        } else {
          toast("Error al ignorar alerta.", false);
        }
      })
      .catch(function () {
        toast("Error de red.", false);
      });
  }

  function toggleDropdown(open) {
    var dd = document.getElementById("arBellDropdown");
    if (!dd) return;
    state.dropdownOpen = open == null ? !state.dropdownOpen : !!open;
    dd.classList.toggle("hidden", !state.dropdownOpen);
    if (state.dropdownOpen) fetchAlertas();
  }

  function init() {
    var bell = document.getElementById("arBellBtn");
    var closeBtn = document.getElementById("arBellClose");
    if (bell) {
      bell.addEventListener("click", function (e) {
        e.stopPropagation();
        toggleDropdown();
      });
    }
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        toggleDropdown(false);
      });
    }
    document.addEventListener("click", function (e) {
      if (!state.dropdownOpen) return;
      var dd = document.getElementById("arBellDropdown");
      if (dd && !dd.contains(e.target) && e.target !== bell && !bell.contains(e.target)) {
        toggleDropdown(false);
      }
    });
    fetchAlertas();
    setInterval(function () {
      fetchAlertas();
    }, POLL_MS);
  }

  window.refreshAdminAlertasRiesgo = function () {
    return fetchAlertas();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
