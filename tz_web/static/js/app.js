// TZ Analyzer — Fase 2 Web. JS propio, sin dependencias externas.
// No usa WebSocket ni Server-Sent Events: el progreso se obtiene por
// sondeo (polling) periódico de /status, tal como pide el encargo.

// Política transversal de teclado para formularios operativos. Enter en un
// campo de datos no elige un submitter implícito; las acciones siguen
// disponibles mediante sus botones explícitos. No se interceptan textarea,
// botones, Space ni controles ajenos a un formulario.
function tzIsExplicitEnterAction(target) {
  if (!target) {
    return false;
  }
  var tagName = String(target.tagName || "").toLowerCase();
  if (tagName === "button") {
    return true;
  }
  if (target.closest && target.closest("button")) {
    return true;
  }
  if (tagName !== "input") {
    return false;
  }
  var inputType = String(target.type || "text").toLowerCase();
  // file y color abren selectores nativos con Enter; no son campos que
  // deban producir un submit implícito y conservarlos evita perder teclado.
  return ["button", "submit", "reset", "image", "file", "color"].indexOf(inputType) !== -1;
}

function tzShouldBlockFormEnter(target) {
  if (!target || tzIsExplicitEnterAction(target)) {
    return false;
  }
  var tagName = String(target.tagName || "").toLowerCase();
  if (tagName === "textarea") {
    return false;
  }
  if (tagName !== "input" && tagName !== "select") {
    return false;
  }
  var form = target.form;
  if (!form && target.closest) {
    form = target.closest("form");
  }
  return Boolean(form);
}

function tzHandleFormKeydown(event) {
  if (!event || event.key !== "Enter" || event.isComposing || event.defaultPrevented) {
    return;
  }
  if (tzShouldBlockFormEnter(event.target)) {
    event.preventDefault();
  }
}

function tzInstallFormEnterGuard(root) {
  if (!root || typeof root.addEventListener !== "function") {
    return;
  }
  root.addEventListener("keydown", tzHandleFormKeydown);
}

// Los botones de navegación regresiva son type=button para que nunca puedan
// convertirse en el submitter implícito. Al activarlos con clic, Enter o Space,
// este helper reproduce su POST explícito y conserva la validación nativa.
function tzSubmitExplicitFormAction(button) {
  var form = button && button.form;
  if (!form) {
    return;
  }

  var submitter = document.createElement("button");
  submitter.type = "submit";
  submitter.hidden = true;
  submitter.tabIndex = -1;
  submitter.setAttribute("aria-hidden", "true");
  if (button.name) {
    submitter.name = button.name;
    submitter.value = button.value;
  }
  form.appendChild(submitter);
  try {
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit(submitter);
    } else {
      submitter.click();
    }
  } finally {
    form.removeChild(submitter);
  }
}

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

// UX posterior a un error de validación del mapeo (server-side sigue
// siendo la fuente de verdad: esta función solo desplaza la vista al
// primer campo ya señalado como conflictivo por el servidor).
function tzMappingFocusConflict(camposConflictivos) {
  if (!camposConflictivos || !camposConflictivos.length) {
    return;
  }
  var fila = document.querySelector('.tz-mapping-row[data-campo="' + camposConflictivos[0] + '"]');
  if (!fila) {
    return;
  }
  var grupo = fila.closest('.tz-mapping-group');
  if (grupo) {
    var indice = parseInt(grupo.getAttribute('data-group-index'), 10);
    if (!isNaN(indice)) {
      tzMappingCurrentGroup = indice;
      tzMappingRender();
    }
  }
  fila.scrollIntoView({ behavior: 'smooth', block: 'center' });
  var foco = fila.querySelector('select, input[type="text"]');
  if (foco && foco.focus) {
    foco.focus();
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

// ---------------------------------------------------------------------------
// Selector de carpeta de salida (MICROBLOQUE 6) — configure_final.html
// (Modo 1/2) y modo3_preparar.html comparten este mismo botón/endpoint.
// El diálogo nativo puede tardar lo que el usuario decida: el botón se
// deshabilita mientras espera la respuesta para evitar clics duplicados,
// pero nunca bloquea el resto de la página ni el resto del formulario.
// ---------------------------------------------------------------------------

function tzSeleccionarCarpetaSalida() {
  var btn = document.getElementById("btn_seleccionar_carpeta");
  var texto = document.getElementById("carpeta_salida_texto");
  var errorBox = document.getElementById("carpeta_salida_error");
  if (!btn || !texto) {
    return;
  }
  if (errorBox) {
    errorBox.style.display = "none";
    errorBox.textContent = "";
  }
  var textoOriginal = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Abriendo selector…";

  fetch("/output-folder/select", {
    method: "POST",
    credentials: "same-origin",
  })
    .then(function (resp) {
      return resp.json().catch(function () {
        return null;
      });
    })
    .then(function (data) {
      if (!data) {
        throw new Error("Respuesta inválida del selector de carpetas.");
      }
      if (data.status === "ok") {
        texto.textContent = data.carpeta_salida;
      } else if (data.status === "cancelled") {
        // Cancelado: la selección existente (si la había) no cambia.
      } else if (errorBox) {
        errorBox.textContent = data.message || "No se pudo seleccionar la carpeta. Intente nuevamente.";
        errorBox.style.display = "";
      }
    })
    .catch(function () {
      if (errorBox) {
        errorBox.textContent = "No se pudo comunicar con TZ Analyzer para abrir el selector. Intente nuevamente.";
        errorBox.style.display = "";
      }
    })
    .finally(function () {
      btn.disabled = false;
      btn.textContent = textoOriginal;
    });
}

// ---------------------------------------------------------------------------
// AYUDA (MICROBLOQUE 6-2): abre el manual de usuario en una ventana/pestaña
// nombrada estable, reutilizada si ya está abierta. Nunca navega la pestaña
// operativa actual — el análisis, mapeo o configuración en curso no se ve
// afectado por abrir/cerrar la ayuda.
// ---------------------------------------------------------------------------

function tzAbrirAyuda() {
  window.open("/help", "tz_analyzer_help");
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

var TZ_POLL_MAX_CONSECUTIVE_FAILURES = 4;
var TZ_POLL_STATUS_ERROR_MESSAGE =
  "No se pudo consultar el estado del análisis. Verifique que TZ Analyzer continúe abierto.";

function tzStartPolling(statusUrl, resultsUrl) {
  var fill = document.getElementById("tz-progress-fill");
  var label = document.getElementById("tz-progress-label");
  var stageItems = document.querySelectorAll("#tz-stage-list li");
  var consecutiveFailures = 0;
  var pollingStopped = false;
  var stageOrder = Array.prototype.map.call(stageItems, function (li) {
    return li.getAttribute("data-stage");
  });

  function applyState(data) {
    if (fill) {
      fill.style.width = data.percent + "%";
    }
    if (label) {
      label.textContent = data.percent + "% — " + (data.stage_label || data.message || "Procesando");
    }
    var currentIndex = stageOrder.indexOf(data.stage);
    stageItems.forEach(function (li, index) {
      var isCurrent = li.getAttribute("data-stage") === data.stage;
      li.classList.toggle("current", isCurrent);
      li.classList.toggle("done", !isCurrent && currentIndex > -1 && index < currentIndex);
    });
  }

  function scheduleNextPoll(delay) {
    if (!pollingStopped) {
      window.setTimeout(poll, delay);
    }
  }

  function handlePollingFailure() {
    consecutiveFailures += 1;
    if (consecutiveFailures >= TZ_POLL_MAX_CONSECUTIVE_FAILURES) {
      pollingStopped = true;
      if (label) {
        label.textContent = TZ_POLL_STATUS_ERROR_MESSAGE;
      }
      return;
    }
    scheduleNextPoll(2000);
  }

  function poll() {
    if (pollingStopped) {
      return;
    }
    fetch(statusUrl, { credentials: "same-origin" })
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("HTTP status request failed");
        }
        return resp.json();
      })
      .then(function (data) {
        applyState(data);
        consecutiveFailures = 0;
        if (data.status === "success" || data.status === "partial" || data.status === "failed") {
          window.location.href = resultsUrl;
          return;
        }
        scheduleNextPoll(1500);
      })
      .catch(handlePollingFailure);
  }

  poll();
}

// ---------------------------------------------------------------------------
// Ciclo de vida del backend (MICROBLOQUE 5): heartbeat mientras la pestaña
// está abierta y cierre explícito ("Cerrar TZ Analyzer"). El token viaja en
// una cabecera propia, nunca en la URL — ver tz_web/templates/base.html
// (meta[name=tz-token]) y tz_web/internal_routes.py.
// ---------------------------------------------------------------------------

var TZ_HEARTBEAT_INTERVAL_MS = 60000;

function tzGetInstanceToken() {
  var meta = document.querySelector('meta[name="tz-token"]');
  return meta ? meta.content : "";
}

function tzStartHeartbeat() {
  var token = tzGetInstanceToken();
  if (!token) {
    return;
  }
  function beat() {
    fetch("/internal/heartbeat", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-TZ-Token": token },
    }).catch(function () {
      // Sin conectividad momentánea con el propio backend local: el
      // siguiente heartbeat lo reintenta; no hay nada que mostrar al
      // usuario por un solo fallo aislado.
    });
  }
  beat();
  window.setInterval(beat, TZ_HEARTBEAT_INTERVAL_MS);
}

function tzRequestShutdown() {
  var token = tzGetInstanceToken();
  if (!token) {
    return;
  }
  if (!window.confirm("¿Cerrar TZ Analyzer? Si hay un análisis en curso, continuará hasta terminar y luego se cerrará.")) {
    return;
  }
  fetch("/internal/shutdown", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-TZ-Token": token },
  })
    .then(function (resp) {
      return resp.json();
    })
    .then(function (data) {
      var mensaje = data.lifecycle_state === "CLOSE_WHEN_IDLE"
        ? "Hay un análisis en curso. TZ Analyzer se cerrará automáticamente al finalizar."
        : "TZ Analyzer se está cerrando.";
      window.alert(mensaje);
    })
    .catch(function () {
      window.alert("No se pudo solicitar el cierre de TZ Analyzer. Intente nuevamente.");
    });
}
