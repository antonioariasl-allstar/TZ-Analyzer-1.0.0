"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const APP_JS = fs.readFileSync(
  path.resolve(__dirname, "../../tz_web/static/js/app.js"),
  "utf8"
);
const EXPECTED_ERROR =
  "No se pudo consultar el estado del análisis. Verifique que TZ Analyzer continúe abierto.";

function createHarness(outcomes) {
  const pendingTimers = [];
  const requests = [];
  const label = { textContent: "Procesando" };
  let jsonCalls = 0;

  const context = {
    document: {
      getElementById(id) {
        return id === "tz-progress-label" ? label : null;
      },
      querySelectorAll() {
        return [];
      },
    },
    window: {
      location: { href: "" },
      setTimeout(callback, delay) {
        pendingTimers.push({ callback, delay });
      },
    },
    fetch(url, options) {
      requests.push({ url, options });
      const outcome = outcomes.shift();
      assert.ok(outcome, "La prueba debe proveer una respuesta por cada sondeo.");

      if (outcome === "network-error") {
        return Promise.reject(new Error("connection refused"));
      }
      if (outcome === "http-error") {
        return Promise.resolve({
          ok: false,
          json() {
            jsonCalls += 1;
            throw new Error("No debe intentar leer JSON de una respuesta HTTP no OK.");
          },
        });
      }
      if (outcome === "invalid-json") {
        return Promise.resolve({
          ok: true,
          json() {
            jsonCalls += 1;
            return Promise.reject(new SyntaxError("Unexpected token"));
          },
        });
      }
      return Promise.resolve({
        ok: true,
        json() {
          jsonCalls += 1;
          return Promise.resolve(outcome);
        },
      });
    },
  };

  vm.createContext(context);
  vm.runInContext(APP_JS, context, { filename: "app.js" });

  async function settle() {
    await new Promise((resolve) => setImmediate(resolve));
  }

  async function runNextTimer(expectedDelay) {
    assert.ok(pendingTimers.length, "Se esperaba un nuevo intento programado.");
    const timer = pendingTimers.shift();
    assert.equal(timer.delay, expectedDelay);
    timer.callback();
    await settle();
  }

  return {
    context,
    jsonCalls: () => jsonCalls,
    label,
    pendingTimers,
    requests,
    runNextTimer,
    async start() {
      context.tzStartPolling("/status", "/results");
      await settle();
    },
  };
}

test("detiene el polling tras cuatro errores HTTP consecutivos", async () => {
  const harness = createHarness([
    "http-error",
    "http-error",
    "http-error",
    "http-error",
  ]);

  await harness.start();
  assert.equal(harness.context.TZ_POLL_MAX_CONSECUTIVE_FAILURES, 4);
  await harness.runNextTimer(2000);
  await harness.runNextTimer(2000);
  await harness.runNextTimer(2000);

  assert.equal(harness.requests.length, 4);
  assert.equal(harness.jsonCalls(), 0);
  assert.equal(harness.pendingTimers.length, 0);
  assert.equal(harness.label.textContent, EXPECTED_ERROR);
  harness.requests.forEach(({ url, options }) => {
    assert.equal(url, "/status");
    assert.deepEqual({ ...options }, { credentials: "same-origin" });
  });
});

test("trata JSON inválido como fallo consecutivo y termina con mensaje claro", async () => {
  const harness = createHarness([
    "invalid-json",
    "invalid-json",
    "invalid-json",
    "invalid-json",
  ]);

  await harness.start();
  await harness.runNextTimer(2000);
  await harness.runNextTimer(2000);
  await harness.runNextTimer(2000);

  assert.equal(harness.jsonCalls(), 4);
  assert.equal(harness.pendingTimers.length, 0);
  assert.equal(harness.label.textContent, EXPECTED_ERROR);
});

test("una respuesta válida antes del umbral reinicia el contador", async () => {
  const running = {
    percent: 45,
    stage: "cargando_archivo",
    stage_label: "Cargando archivo",
    status: "running",
  };
  const harness = createHarness([
    "network-error",
    "network-error",
    "network-error",
    running,
    "http-error",
    "http-error",
    "http-error",
    running,
  ]);

  await harness.start();
  await harness.runNextTimer(2000);
  await harness.runNextTimer(2000);
  await harness.runNextTimer(2000);
  assert.equal(harness.label.textContent, "45% — Cargando archivo");

  await harness.runNextTimer(1500);
  await harness.runNextTimer(2000);
  await harness.runNextTimer(2000);
  await harness.runNextTimer(2000);

  assert.equal(harness.requests.length, 8);
  assert.equal(harness.label.textContent, "45% — Cargando archivo");
  assert.notEqual(harness.label.textContent, EXPECTED_ERROR);
  assert.equal(harness.pendingTimers.length, 1);
  assert.equal(harness.pendingTimers[0].delay, 1500);
});

test("partial es terminal y redirige a resultados", async () => {
  const harness = createHarness([{
    percent: 100,
    stage: "finalizado",
    stage_label: "AnÃ¡lisis finalizado parcialmente",
    status: "partial",
  }]);

  await harness.start();

  assert.equal(harness.context.window.location.href, "/results");
  assert.equal(harness.pendingTimers.length, 0);
});
