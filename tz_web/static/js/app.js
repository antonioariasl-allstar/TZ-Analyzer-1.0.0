// TZ Analyzer — Fase 2 Web. JS propio, sin dependencias externas.
// No usa WebSocket ni Server-Sent Events: el progreso se obtiene por
// sondeo (polling) periódico de /status, tal como pide el encargo.

function tzHandleFileSelect(input) {
  var wrap = document.getElementById("archivo_seleccionado");
  var nameEl = document.getElementById("archivo_nombre");
  var btn = document.getElementById("btn_cargar");

  if (!input.files || input.files.length === 0) {
    if (wrap) wrap.hidden = true;
    if (btn) btn.disabled = true;
    return;
  }

  if (nameEl) nameEl.textContent = input.files[0].name;
  if (wrap) wrap.hidden = false;
  if (btn) btn.disabled = false;
}

function tzToggleMappingRow(campo) {
  var colRadio = document.getElementById("tipo_col_" + campo);
  var colWrap = document.getElementById("col_wrap_" + campo);
  if (!colRadio || !colWrap) {
    return;
  }
  colWrap.style.display = colRadio.checked ? "" : "none";
}

// Paginado del formulario de mapeo (sección 3): todos los campos permanecen
// en el DOM, solo se oculta/muestra un grupo a la vez. Sin envíos parciales.
var TZ_MAPPING_GROUP_NAMES = [];
var tzMappingCurrentGroup = 0;

function tzMappingInit(groupNames) {
  TZ_MAPPING_GROUP_NAMES = groupNames || [];
  tzMappingCurrentGroup = 0;
  tzMappingRender();
}

function tzMappingRender() {
  var groups = document.querySelectorAll(".tz-mapping-group");
  if (!groups.length) {
    return;
  }
  groups.forEach(function (g) {
    g.hidden = parseInt(g.getAttribute("data-group-index"), 10) !== tzMappingCurrentGroup;
  });

  var label = document.getElementById("mapping_group_label");
  if (label) {
    var nombre = TZ_MAPPING_GROUP_NAMES[tzMappingCurrentGroup] || "";
    label.textContent = "Grupo " + (tzMappingCurrentGroup + 1) + " de " + groups.length + " — " + nombre;
  }

  var isFirst = tzMappingCurrentGroup === 0;
  var isLast = tzMappingCurrentGroup === groups.length - 1;
  var prevBtn = document.getElementById("mapping_btn_prev");
  var nextBtn = document.getElementById("mapping_btn_next");
  var submitBtn = document.getElementById("mapping_btn_submit");
  if (prevBtn) prevBtn.hidden = isFirst;
  if (nextBtn) nextBtn.hidden = isLast;
  if (submitBtn) submitBtn.hidden = !isLast;
}

function tzMappingNext() {
  var groups = document.querySelectorAll(".tz-mapping-group");
  if (tzMappingCurrentGroup < groups.length - 1) {
    tzMappingCurrentGroup += 1;
    tzMappingRender();
  }
}

function tzMappingPrev() {
  if (tzMappingCurrentGroup > 0) {
    tzMappingCurrentGroup -= 1;
    tzMappingRender();
  }
}

function tzToggleFiltro() {
  var tipo = document.getElementById("filtro_tipo");
  if (!tipo) {
    return;
  }
  var diaWrap = document.getElementById("filtro_wrap_dia");
  var rangoDiasWrap = document.getElementById("filtro_wrap_rango_dias");
  var horasWrap = document.getElementById("filtro_wrap_horas");

  var valor = tipo.value;
  if (diaWrap) diaWrap.style.display = (valor === "dia" || valor === "rango_horas_dia") ? "" : "none";
  if (rangoDiasWrap) rangoDiasWrap.style.display = valor === "rango_dias" ? "" : "none";
  if (horasWrap) horasWrap.style.display = (valor === "rango_horas_dia" || valor === "rango_horas") ? "" : "none";
}

function tzGuardStartButton(button) {
  if (button.dataset.tzSubmitted === "1") {
    return false;
  }
  button.dataset.tzSubmitted = "1";
  button.disabled = true;
  button.textContent = "Iniciando…";
  return true;
}

function tzStartPolling(statusUrl, resultsUrl) {
  var fill = document.getElementById("tz-progress-fill");
  var label = document.getElementById("tz-progress-label");
  var stageItems = document.querySelectorAll("#tz-stage-list li");

  function applyState(data) {
    if (fill) {
      fill.style.width = data.percent + "%";
    }
    if (label) {
      label.textContent = data.percent + "% — " + (data.stage_label || data.message || "Procesando");
    }
    stageItems.forEach(function (li) {
      li.classList.toggle("current", li.getAttribute("data-stage") === data.stage);
    });
  }

  function poll() {
    fetch(statusUrl, { credentials: "same-origin" })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        applyState(data);
        if (data.status === "success" || data.status === "failed") {
          window.location.href = resultsUrl;
          return;
        }
        window.setTimeout(poll, 1500);
      })
      .catch(function () {
        window.setTimeout(poll, 2000);
      });
  }

  poll();
}
