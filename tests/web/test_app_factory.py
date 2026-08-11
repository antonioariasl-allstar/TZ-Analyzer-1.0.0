"""FASE 2 WEB — create_app(), configuración del servidor y pantalla inicial."""
from __future__ import annotations

import builtins

from tz_web.app import HOST, create_app


def test_create_app_devuelve_una_app_flask_configurada(app):
    assert app is not None
    assert app.config["SECRET_KEY"]
    assert app.config["MAX_CONTENT_LENGTH"] > 0


def test_host_configurado_como_127_0_0_1():
    assert HOST == "127.0.0.1"


def test_secret_key_es_distinta_entre_instancias():
    app1 = create_app()
    app2 = create_app()
    assert app1.config["SECRET_KEY"] != app2.config["SECRET_KEY"]


def test_portada_responde_200_y_muestra_boton_entrar(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TZ ANALYZER".encode("utf-8") in resp.data
    assert "ENTRAR AL ANALIZADOR".encode("utf-8") in resp.data


def test_menu_principal_muestra_los_tres_modos(client):
    resp = client.get("/menu")
    assert resp.status_code == 200
    assert "Procesar bitácora completa".encode("utf-8") in resp.data
    assert "Procesar bitácora filtrada por tiempo".encode("utf-8") in resp.data
    assert "Mapear antenas y ubicaciones manualmente".encode("utf-8") in resp.data


def test_modo_1_abre_la_pantalla_de_carga_de_archivo(client):
    resp = client.post("/modo/1", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Cargar archivo" in resp.data
    assert b'enctype="multipart/form-data"' in resp.data


def test_modo_3_ya_no_esta_pendiente(client):
    resp = client.post("/modo/3", follow_redirects=True)
    assert resp.status_code == 200
    assert "Modo pendiente de incorporación web".encode("utf-8") not in resp.data
    assert "¿Qué tipo de registros desea agregar?".encode("utf-8") in resp.data


def test_modo_2_ya_no_esta_pendiente(client):
    resp = client.post("/modo/2", follow_redirects=True)
    assert resp.status_code == 200
    assert "Modo pendiente de incorporación web".encode("utf-8") not in resp.data
    assert b"Cargar archivo" in resp.data


def test_pantallas_del_modo_1_incluyen_boton_volver_al_menu(client):
    resp = client.post("/modo/1", follow_redirects=True)
    assert "Volver al menú principal".encode("utf-8") in resp.data


def test_encabezado_no_muestra_ip_local(client):
    resp = client.post("/modo/1", follow_redirects=True)
    assert b"127.0.0.1" not in resp.data
    assert "Aplicación local".encode("utf-8") in resp.data


def test_pie_de_pagina_muestra_las_tres_lineas(client):
    resp = client.post("/modo/1", follow_redirects=True)
    assert "Procesamiento local".encode("utf-8") in resp.data
    assert "Desarrollado por Omar Arias (Tony Zero)".encode("utf-8") in resp.data
    assert "Los datos y archivos permanecen en este equipo.".encode("utf-8") in resp.data


def test_menu_muestra_enlace_volver_a_portada_y_distintivos_numerados(client):
    resp = client.get("/menu")
    assert "Volver a la portada".encode("utf-8") in resp.data
    assert b'class="tz-menu-badge">1<' in resp.data
    assert b'class="tz-menu-badge">2<' in resp.data
    assert b'class="tz-menu-badge">3<' in resp.data


def test_importar_tz_web_no_altera_builtins_input():
    """Proxy de 'CLI intacta': importar la capa web no debe monkeypatchear
    builtins.input ni ningún estado global usado por el CLI interactivo."""
    original = builtins.input
    import tz_web.app  # noqa: F401
    import tz_web.routes  # noqa: F401
    import tz_web.state  # noqa: F401

    assert builtins.input is original


def test_cli_run_py_sigue_siendo_importable_sin_tz_web():
    """El launcher CLI (tz_core.app_runner.run) no depende de tz_web ni se ve
    afectado por su existencia."""
    from tz_core.app_runner import run

    assert callable(run)
