"""Contrato transversal de teclado y tipos de botones (MB7-A3)."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "tz_web" / "templates"
APP_JS = ROOT / "tz_web" / "static" / "js" / "app.js"


class _ButtonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.buttons: list[dict[str, object]] = []
        self._button: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "button":
            self._button = {"attrs": dict(attrs), "text": []}

    def handle_data(self, data: str) -> None:
        if self._button is not None:
            self._button["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._button is not None:
            self._button["text"] = " ".join(
                "".join(self._button["text"]).split()
            )
            self.buttons.append(self._button)
            self._button = None


def _source(template_name: str) -> str:
    return (TEMPLATES / template_name).read_text(encoding="utf-8")


def _buttons(template_name: str) -> list[dict[str, object]]:
    parser = _ButtonParser()
    parser.feed(_source(template_name))
    return parser.buttons


def _button_by_id(template_name: str, button_id: str) -> dict[str, object]:
    return next(
        button
        for button in _buttons(template_name)
        if button["attrs"].get("id") == button_id
    )


def _is_backward_navigation(button: dict[str, object]) -> bool:
    text = str(button["text"]).casefold()
    return (
        "anterior" in text
        or "volver" in text
        or text in {"cambiar archivo", "cambiar hoja"}
    )


def test_todos_los_botones_declaran_un_type_valido() -> None:
    found = 0
    for path in sorted(TEMPLATES.glob("*.html")):
        for button in _buttons(path.name):
            found += 1
            button_type = button["attrs"].get("type")
            assert button_type in {"button", "submit"}, (
                f"{path.name}: botón sin type explícito válido: {button['text']!r}"
            )
    assert found > 0


def test_navegacion_regresiva_no_es_submitter_implicito() -> None:
    backward_buttons = []
    for path in sorted(TEMPLATES.glob("*.html")):
        for button in _buttons(path.name):
            if _is_backward_navigation(button):
                backward_buttons.append((path.name, button))

    assert backward_buttons
    for template_name, button in backward_buttons:
        attrs = button["attrs"]
        assert attrs.get("type") == "button", (
            f"{template_name}: navegación regresiva aún es submit: {button['text']!r}"
        )
        if attrs.get("id") != "mapping_btn_prev":
            assert attrs.get("onclick") == "tzSubmitExplicitFormAction(this)"


def test_acciones_reales_de_avance_conservan_submit_explicito() -> None:
    client_button_ids = {
        "btn_seleccionar_carpeta",
        "mapping_btn_next",
        "mapping_btn_prev",
        "tz-help-nav-toggle",
    }
    client_button_texts = {
        "ayuda",
        "salir",
        "cambiar nombre",
        "usar nombre sugerido",
        "índice",
        "seleccionar carpeta…",
    }
    submit_buttons = []
    for path in sorted(TEMPLATES.glob("*.html")):
        for button in _buttons(path.name):
            attrs = button["attrs"]
            text = str(button["text"]).casefold()
            is_client_action = (
                attrs.get("id") in client_button_ids or text in client_button_texts
            )
            if not _is_backward_navigation(button) and not is_client_action:
                submit_buttons.append((path.name, button))

    assert submit_buttons
    for template_name, button in submit_buttons:
        assert button["attrs"].get("type") == "submit", (
            f"{template_name}: la acción real {button['text']!r} debe ser submit"
        )


def test_hay_una_sola_politica_transversal_sin_bloqueos_locales() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")
    base = _source("base.html")
    all_templates = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(TEMPLATES.glob("*.html"))
    )

    assert "function tzShouldBlockFormEnter" in app_js
    assert "function tzHandleFormKeydown" in app_js
    assert "tzInstallFormEnterGuard(document)" in base
    assert "onkeydown=" not in all_templates
    assert "noSubmitAdvanceTo" not in all_templates


@pytest.mark.parametrize(
    ("mode", "template_names"),
    [
        (
            "modo_1",
            [
                "index.html",
                "preview.html",
                "mapping.html",
                "configure_identity.html",
                "configure_options.html",
                "configure_outputs.html",
                "configure_color.html",
                "configure_final.html",
                "configure_resumen.html",
                "configure.html",
            ],
        ),
        (
            "modo_2",
            [
                "index.html",
                "preview.html",
                "mapping.html",
                "configure_filtro_tiempo.html",
                "configure_identity.html",
                "configure_options.html",
                "configure_outputs.html",
                "configure_color.html",
                "configure_final.html",
                "configure_resumen.html",
                "configure.html",
            ],
        ),
        (
            "modo_3",
            [
                "modo3_tipo.html",
                "modo3_registros.html",
                "modo3_productos.html",
                "configure_color.html",
                "modo3_preparar.html",
                "modo3_resumen.html",
            ],
        ),
    ],
)
def test_cada_modo_operativo_hereda_la_guarda_global(
    mode: str, template_names: list[str]
) -> None:
    for template_name in template_names:
        source = _source(template_name)
        assert '{% extends "base.html" %}' in source, f"{mode}: {template_name}"
        assert "onkeydown=" not in source, f"{mode}: {template_name}"


def test_mapping_separa_paginado_y_submit_final() -> None:
    previous = _button_by_id("mapping.html", "mapping_btn_prev")
    following = _button_by_id("mapping.html", "mapping_btn_next")
    submit = _button_by_id("mapping.html", "mapping_btn_submit")

    assert previous["attrs"].get("type") == "button"
    assert following["attrs"].get("type") == "button"
    assert submit["attrs"].get("type") == "submit"
    assert "<select" in _source("mapping.html")


@pytest.mark.parametrize("template_name", ["configure_final.html", "modo3_preparar.html"])
def test_selector_y_cambio_de_nombre_son_botones_explicitos(template_name: str) -> None:
    buttons = _buttons(template_name)
    selector = next(button for button in buttons if button["attrs"].get("id") == "btn_seleccionar_carpeta")
    change_name = next(button for button in buttons if "CAMBIAR NOMBRE" in str(button["text"]))

    assert selector["attrs"].get("type") == "button"
    assert selector["attrs"].get("onclick") == "tzSeleccionarCarpetaSalida()"
    assert change_name["attrs"].get("type") == "button"


def test_ayuda_salir_y_omitir_conservan_su_tipo_funcional() -> None:
    base_buttons = _buttons("base.html")
    identity_buttons = _buttons("configure_identity.html")

    for label in ("AYUDA", "SALIR"):
        button = next(item for item in base_buttons if item["text"] == label)
        assert button["attrs"].get("type") == "button"
    omit = next(item for item in identity_buttons if item["text"] == "Omitir")
    assert omit["attrs"].get("type") == "submit"


def test_texto_obsoleto_desaparece_y_se_explica_el_sufijo_por_colision() -> None:
    old_text = "identificador de ejecución"
    new_text = (
        "Si ya existe una carpeta con el mismo nombre, TZ Analyzer añadirá "
        "automáticamente un sufijo para evitar sobrescribir resultados anteriores."
    )
    all_templates = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(TEMPLATES.glob("*.html"))
    )

    assert old_text.casefold() not in all_templates.casefold()
    for template_name in ("configure_final.html", "modo3_preparar.html"):
        normalized = " ".join(_source(template_name).split())
        assert new_text in normalized
