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

function loadApp(extraContext = {}) {
  const context = {
    document: {},
    window: {},
    ...extraContext,
  };
  vm.createContext(context);
  vm.runInContext(APP_JS, context, { filename: "app.js" });
  return context;
}

function formControl(tagName, options = {}) {
  const form = Object.prototype.hasOwnProperty.call(options, "form")
    ? options.form
    : {};
  return {
    tagName: tagName.toUpperCase(),
    type: options.type || "text",
    form,
    closest(selector) {
      if (selector === "form") return form;
      if (selector === "button" && options.insideButton) return {};
      return null;
    },
  };
}

function dispatchKeydown(context, target, key = "Enter", options = {}) {
  let preventions = 0;
  const event = {
    key,
    target,
    isComposing: Boolean(options.isComposing),
    defaultPrevented: Boolean(options.defaultPrevented),
    preventDefault() {
      preventions += 1;
      this.defaultPrevented = true;
    },
  };
  context.tzHandleFormKeydown(event);
  return { event, preventions };
}

test("Enter en input de formulario cancela el submit implícito", () => {
  const context = loadApp();
  const inputTypes = [
    "text", "number", "date", "time", "radio", "checkbox",
  ];

  inputTypes.forEach((type) => {
    const result = dispatchKeydown(context, formControl("input", { type }));
    assert.equal(result.preventions, 1, `input[type=${type}] debe bloquear Enter`);
  });
});

test("Enter en select cancela el submit implícito", () => {
  const context = loadApp();
  const result = dispatchKeydown(context, formControl("select"));

  assert.equal(result.preventions, 1);
});

test("Enter en textarea conserva el salto de línea nativo", () => {
  const context = loadApp();
  const result = dispatchKeydown(context, formControl("textarea"));

  assert.equal(result.preventions, 0);
});

test("Enter y Space sobre button conservan su activación nativa", () => {
  const context = loadApp();
  let nativeActivations = 0;
  const button = formControl("button", { type: "button" });

  ["Enter", " "].forEach((key) => {
    const result = dispatchKeydown(context, button, key);
    if (!result.event.defaultPrevented) nativeActivations += 1;
  });

  assert.equal(nativeActivations, 2);
});

test("controles activables equivalentes y elementos fuera de form no se bloquean", () => {
  const context = loadApp();

  ["button", "submit", "reset", "image", "file", "color"].forEach((type) => {
    const result = dispatchKeydown(context, formControl("input", { type }));
    assert.equal(result.preventions, 0, `input[type=${type}] debe conservar Enter`);
  });
  assert.equal(
    dispatchKeydown(context, formControl("input", { form: null })).preventions,
    0
  );
});

test("Enter no alcanza ningún submitter implícito ni puede elegir Anterior", () => {
  const context = loadApp();
  const form = {
    controls: [
      { type: "button", name: "accion", value: "anterior" },
      { type: "submit", name: "accion", value: "siguiente" },
    ],
    submittedValues: [],
    runImplicitSubmit() {
      const submitter = this.controls.find((control) => control.type === "submit");
      if (submitter) this.submittedValues.push(submitter.value);
    },
  };
  const result = dispatchKeydown(context, formControl("input", { form }));

  if (!result.event.defaultPrevented) form.runImplicitSubmit();

  assert.deepEqual(form.submittedValues, []);
  assert.equal(form.controls[0].type, "button");
});

test("Anterior se envía una sola vez solo al activar su type=button", () => {
  const created = [];
  const context = loadApp({
    document: {
      createElement(tagName) {
        const element = {
          tagName: tagName.toUpperCase(),
          attributes: {},
          clickCalls: 0,
          setAttribute(name, value) {
            this.attributes[name] = value;
          },
          click() {
            this.clickCalls += 1;
          },
        };
        created.push(element);
        return element;
      },
    },
  });
  const children = [];
  const submitted = [];
  const form = {
    appendChild(element) {
      children.push(element);
    },
    removeChild(element) {
      assert.equal(children.pop(), element);
    },
    requestSubmit(submitter) {
      assert.equal(children.includes(submitter), true);
      submitted.push({
        type: submitter.type,
        name: submitter.name,
        value: submitter.value,
      });
    },
  };
  const backButton = {
    type: "button",
    name: "accion",
    value: "anterior",
    form,
  };

  context.tzSubmitExplicitFormAction(backButton);

  assert.deepEqual(submitted, [{ type: "submit", name: "accion", value: "anterior" }]);
  assert.equal(created.length, 1);
  assert.equal(children.length, 0);
});

test("la guarda se instala como un único listener keydown delegado", () => {
  const context = loadApp();
  const registrations = [];
  const root = {
    addEventListener(type, handler) {
      registrations.push({ type, handler });
    },
  };

  context.tzInstallFormEnterGuard(root);

  assert.equal(registrations.length, 1);
  assert.equal(registrations[0].type, "keydown");
  assert.equal(registrations[0].handler, context.tzHandleFormKeydown);
});
