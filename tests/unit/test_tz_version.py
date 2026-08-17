"""tz_version — fuente canónica única de identidad/versión (FASE 3).

Cubre: valores de las constantes aprobadas, que tz_core.__version__ ya no
diverge, que tz_version es importable sin Flask (compatible con el uso que
hace tz_launcher.py antes de tocar el backend web) y que no introduce
dependencias circulares con tz_core/tz_web.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from datetime import date
from pathlib import Path

import tz_version

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# A — constantes aprobadas.
# ---------------------------------------------------------------------------


def test_version_display():
    assert tz_version.VERSION == "1.0.0-beta.1"


def test_version_pep440():
    assert tz_version.PEP440_VERSION == "1.0.0b1"


def test_windows_file_version():
    assert tz_version.WINDOWS_FILE_VERSION == (1, 0, 0, 1)
    assert tz_version.WINDOWS_FILE_VERSION_STRING == "1.0.0.1"


def test_copyright():
    assert tz_version.COPYRIGHT == (
        "© 2026 Omar Arias (Tony Zero). Todos los derechos reservados."
    )


def test_author():
    assert tz_version.AUTHOR == "Omar Arias (Tony Zero)"


def test_company_name_vacio():
    assert tz_version.COMPANY_NAME == ""


def test_product_identity():
    assert tz_version.PRODUCT_NAME == "TZ Analyzer"
    assert tz_version.PRODUCT_DESCRIPTION == (
        "Análisis de bitácoras telefónicas y georreferenciación"
    )


# ---------------------------------------------------------------------------
# B — tz_core.__version__ ya no diverge de la fuente central.
# ---------------------------------------------------------------------------


def test_tz_core_version_no_diverge():
    import tz_core

    assert tz_core.__version__ == tz_version.PEP440_VERSION
    assert tz_core.__author__ == tz_version.AUTHOR


# ---------------------------------------------------------------------------
# C — tz_version es dependency-free (sin imports de tz_core/tz_web) y no
# tiene efectos secundarios de importación más allá de definir constantes.
# ---------------------------------------------------------------------------


def test_tz_version_sin_imports_de_tz_core_ni_tz_web():
    source = (REPO_ROOT / "tz_version.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(
        mod == "tz_core" or mod.startswith("tz_core.") for mod in imported_modules
    ), f"tz_version.py no debe importar tz_core: {imported_modules}"
    assert not any(
        mod == "tz_web" or mod.startswith("tz_web.") for mod in imported_modules
    ), f"tz_version.py no debe importar tz_web: {imported_modules}"


def test_tz_version_importable_sin_flask():
    # Subproceso aislado: garantiza que importar tz_version, por sí solo, no
    # arrastra Flask (compatible con el uso que tz_launcher.py hace de la
    # versión antes de decidir instancia única / levantar el backend web).
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import tz_version; "
            "assert 'flask' not in sys.modules; "
            "print(tz_version.VERSION)",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.0.0-beta.1"


# ---------------------------------------------------------------------------
# D — sin dependencia circular tz_version <-> tz_core/tz_web.
# ---------------------------------------------------------------------------


def test_sin_dependencia_circular_import_tz_core_primero():
    result = subprocess.run(
        [sys.executable, "-c", "import tz_core; import tz_version"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_sin_dependencia_circular_import_tz_web_app_primero():
    result = subprocess.run(
        [sys.executable, "-c", "import tz_web.app; import tz_version"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# E — protocolo de instancia única no se toca (LAUNCHER_VERSION es un
# número de protocolo, no la versión de producto; FASE 3 no debe alterarlo).
# ---------------------------------------------------------------------------


def test_launcher_version_protocolo_no_se_toca():
    from tz_web.instance import LAUNCHER_VERSION

    assert LAUNCHER_VERSION == "1.0"


# ---------------------------------------------------------------------------
# F — cierre MB-F3C: config.json ya no define la versión de TZ Analyzer;
# tz_version.py es la única fuente canónica en todo el repo.
# ---------------------------------------------------------------------------


def test_config_json_ya_no_tiene_campo_de_version_de_producto():
    import json

    config = json.loads((REPO_ROOT / "config.json").read_text(encoding="utf-8"))
    assert "version" not in config.get("brand", {}), (
        "config.json no debe volver a definir brand.version: "
        "tz_version.VERSION es la única fuente canónica de la versión de producto"
    )
    assert "byline_texto" not in config.get("branding", {}), (
        "config.json no debe volver a definir branding.byline_texto: "
        "el byline del informe se construye desde tz_version (ver MB-F3B)"
    )


def test_runtime_utils_usa_tz_version_no_config():
    from tz_core.runtime_utils import collect_env_snapshot

    config_envenenado = {"version": "9.9.9-residual", "brand": {"version": "8.8.8-residual"}}
    snapshot = collect_env_snapshot(config_envenenado)
    assert snapshot["tz_analysis"] == tz_version.VERSION
    assert "residual" not in snapshot["tz_analysis"]


def test_assembler_sin_lectura_muerta_de_brand_version():
    source = (REPO_ROOT / "tz_core" / "html" / "assembler.py").read_text(encoding="utf-8")
    assert 'get("version"' not in source, (
        "tz_core/html/assembler.py no debe conservar ninguna lectura, "
        "activa o muerta, de una versión declarada en config.json"
    )


# ---------------------------------------------------------------------------
# G — vigencia de la Beta (P1-BETA-EXPIRY): fuente única, fecha inyectable,
# sin depender del reloj real. Contrato: 31/12/2027 vigente, 01/01/2028
# vencida (comparación estricta ">", nunca ">=").
# ---------------------------------------------------------------------------


def test_beta_expires_on_es_31_12_2027():
    assert tz_version.BETA_EXPIRES_ON == date(2027, 12, 31)


def test_2027_12_30_vigente():
    assert tz_version.is_beta_expired(date(2027, 12, 30)) is False


def test_2027_12_31_vigente():
    assert tz_version.is_beta_expired(date(2027, 12, 31)) is False


def test_2028_01_01_vencida():
    assert tz_version.is_beta_expired(date(2028, 1, 1)) is True


def test_2028_01_02_vencida():
    assert tz_version.is_beta_expired(date(2028, 1, 2)) is True


def test_dias_restantes_antes_del_vencimiento():
    assert tz_version.beta_days_remaining(date(2027, 12, 1)) == 30
    assert tz_version.beta_days_remaining(date(2027, 12, 31)) == 0


def test_dias_restantes_negativos_tras_vencer():
    assert tz_version.beta_days_remaining(date(2028, 1, 1)) == -1


def test_aviso_activo_a_30_dias_o_menos():
    status = tz_version.get_beta_status(date(2027, 12, 1))
    assert status.show_warning is True
    assert status.expired is False
    assert status.notice is not None
    assert "30" in status.notice or "días" in status.notice


def test_sin_aviso_a_mas_de_30_dias():
    status = tz_version.get_beta_status(date(2027, 11, 30))
    assert status.days_remaining == 31
    assert status.show_warning is False
    assert status.notice is None


def test_mensaje_hoy_el_dia_del_vencimiento():
    status = tz_version.get_beta_status(date(2027, 12, 31))
    assert status.expired is False
    assert status.show_warning is True
    assert status.notice is not None
    assert "hoy" in status.notice.lower()


def test_get_beta_status_vencida_usa_mensaje_de_beta_vencida():
    status = tz_version.get_beta_status(date(2028, 1, 1))
    assert status.expired is True
    assert status.notice == tz_version.BETA_EXPIRED_NOTICE


def test_beta_expired_notice_no_usa_lenguaje_comercial():
    notice = tz_version.BETA_EXPIRED_NOTICE.lower()
    for termino_prohibido in ("licencia expirada", "producto bloqueado"):
        assert termino_prohibido not in notice


def test_get_beta_status_sin_fecha_usa_hoy():
    assert tz_version.get_beta_status().days_remaining == tz_version.beta_days_remaining()


def test_beta_usage_notice_menciona_evaluacion_y_vigencia():
    notice = tz_version.BETA_USAGE_NOTICE
    assert "evaluación" in notice
    assert "31 de diciembre de 2027" in notice
    assert "gratuita" in notice
    assert "autorización" in notice
