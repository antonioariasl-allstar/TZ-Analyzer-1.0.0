"""Protocolo local para el selector de carpeta ejecutado en un proceso hijo.

Este modulo es deliberadamente una hoja: solo usa la biblioteca estandar y
no importa ``tz_core`` ni ``tz_web``. Asi, el modo interno del ejecutable
puede resolver el dialogo antes de cargar Flask, Waitress o el ciclo de vida
normal de TZ Analyzer.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Optional

INTERNAL_MODE_ARGUMENT = "--tz-internal-folder-dialog"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CANCELLED = 3
EXIT_NO_GUI = 4

PROTOCOL_SCHEMA = "TZ_FOLDER_DIALOG_IPC_V1"
STATUS_SUCCESS = "SUCCESS"
STATUS_CANCELLED = "CANCELLED"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_ERROR = "ERROR"

DIALOG_IPC_TTL_SECONDS = 24 * 60 * 60

_APP_DIR_NAME = "TZ Analyzer"
_REQUEST_ID_RE = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST_KEYS = {"schema", "request_id", "title", "initial_dir"}
_RESULT_KEYS = {"schema", "request_id", "status", "path", "error_code"}
_STALE_EXCHANGE_RE = re.compile(
    r"dialog-(?P<kind>request|result)-(?P<request_id>[0-9a-f]{64})\.json\Z"
)
_STALE_TEMPORARY_RE = re.compile(
    r"\.dialog-(?:request|result)-[0-9a-f]{64}-[a-z0-9_]{8}\.tmp\Z"
)


class DialogProtocolError(ValueError):
    """El intercambio local no cumple el contrato esperado."""


def validate_request_id(request_id: object) -> str:
    """Acepta exclusivamente identificadores aleatorios hexadecimales."""
    if not isinstance(request_id, str) or _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise DialogProtocolError("Identificador interno de dialogo invalido.")
    return request_id


def get_dialog_dir(
    *,
    localappdata: Optional[str] = None,
) -> Path:
    """Directorio tecnico del IPC bajo LocalAppData; no contiene casos."""
    base = localappdata if localappdata is not None else os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / _APP_DIR_NAME / "run" / "dialog"


def _dialog_cleanup_location(dialog_dir: Optional[Path]) -> tuple[Path, Path]:
    """Devuelve ancla y destino literales, sin resolver enlaces.

    En operacion normal el ancla confiada es LocalAppData y se inspeccionan
    todos los componentes propios de TZ Analyzer bajo ella. ``dialog_dir``
    es una inyeccion tecnica para pruebas; su padre actua como ancla y el
    directorio inyectado tambien debe superar la inspeccion no-follow.
    """
    if dialog_dir is not None:
        requested = Path(dialog_dir)
        base = Path(os.path.abspath(os.fspath(requested)))
        return base.parent, base

    base = get_dialog_dir()
    anchor = base.parents[2]
    return (
        Path(os.path.abspath(os.fspath(anchor))),
        Path(os.path.abspath(os.fspath(base))),
    )


def _safe_cleanup_directory(anchor: Path, base: Path) -> bool:
    """Valida cada componente bajo ``anchor`` sin seguir symlinks/reparse."""
    try:
        relative = base.relative_to(anchor)
    except ValueError:
        return False
    if not relative.parts:
        return False

    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    current = anchor
    try:
        # El ancla (LocalAppData en produccion) tambien puede ser una
        # junction/reparse. ``follow_symlinks=False`` solo protege el ultimo
        # componente consultado, por eso se valida antes de descender.
        for component in (None, *relative.parts):
            if component is not None:
                current = current / component
            metadata = os.stat(current, follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                return False
            if getattr(metadata, "st_file_attributes", 0) & reparse_flag:
                return False
            if not stat.S_ISDIR(metadata.st_mode):
                return False
    except OSError:
        return False
    return True


def _validated_dialog_dir(dialog_dir: Optional[Path]) -> Path:
    base = Path(dialog_dir) if dialog_dir is not None else get_dialog_dir()
    return base.resolve(strict=False)


def _exchange_path(kind: str, request_id: object, dialog_dir: Optional[Path]) -> Path:
    validated_id = validate_request_id(request_id)
    base = _validated_dialog_dir(dialog_dir)
    candidate = base / f"dialog-{kind}-{validated_id}.json"
    if candidate.parent.resolve(strict=False) != base:
        raise DialogProtocolError("Ruta interna de dialogo invalida.")
    return candidate


def request_path(request_id: object, *, dialog_dir: Optional[Path] = None) -> Path:
    return _exchange_path("request", request_id, dialog_dir)


def result_path(request_id: object, *, dialog_dir: Optional[Path] = None) -> Path:
    return _exchange_path("result", request_id, dialog_dir)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}-",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DialogProtocolError("No se pudo leer el intercambio del dialogo.") from exc
    if not isinstance(payload, dict):
        raise DialogProtocolError("El intercambio del dialogo no es un objeto JSON.")
    return payload


def write_request(
    request_id: object,
    *,
    title: Optional[str],
    initial_dir: Optional[str],
    dialog_dir: Optional[Path] = None,
) -> Path:
    validated_id = validate_request_id(request_id)
    if title is not None and not isinstance(title, str):
        raise DialogProtocolError("Titulo de dialogo invalido.")
    if initial_dir is not None and not isinstance(initial_dir, str):
        raise DialogProtocolError("Carpeta inicial de dialogo invalida.")
    path = request_path(validated_id, dialog_dir=dialog_dir)
    _write_json_atomic(
        path,
        {
            "schema": PROTOCOL_SCHEMA,
            "request_id": validated_id,
            "title": title,
            "initial_dir": initial_dir,
        },
    )
    return path


def read_request(request_id: object, *, dialog_dir: Optional[Path] = None) -> dict[str, Any]:
    validated_id = validate_request_id(request_id)
    payload = _read_json_object(request_path(validated_id, dialog_dir=dialog_dir))
    if set(payload) != _REQUEST_KEYS:
        raise DialogProtocolError("Estructura de solicitud de dialogo invalida.")
    if payload.get("schema") != PROTOCOL_SCHEMA or payload.get("request_id") != validated_id:
        raise DialogProtocolError("Solicitud de dialogo no corresponde al intercambio esperado.")
    if payload.get("title") is not None and not isinstance(payload.get("title"), str):
        raise DialogProtocolError("Titulo de dialogo invalido.")
    if payload.get("initial_dir") is not None and not isinstance(payload.get("initial_dir"), str):
        raise DialogProtocolError("Carpeta inicial de dialogo invalida.")
    return payload


def _validate_result_payload(payload: Mapping[str, Any], request_id: str) -> None:
    if set(payload) != _RESULT_KEYS:
        raise DialogProtocolError("Estructura de resultado de dialogo invalida.")
    if payload.get("schema") != PROTOCOL_SCHEMA or payload.get("request_id") != request_id:
        raise DialogProtocolError("Resultado de dialogo no corresponde al intercambio esperado.")

    status = payload.get("status")
    path = payload.get("path")
    error_code = payload.get("error_code")
    if status not in {STATUS_SUCCESS, STATUS_CANCELLED, STATUS_UNAVAILABLE, STATUS_ERROR}:
        raise DialogProtocolError("Estado de resultado de dialogo invalido.")
    if status == STATUS_SUCCESS:
        if not isinstance(path, str) or not path:
            raise DialogProtocolError("Ruta seleccionada invalida.")
        if error_code is not None:
            raise DialogProtocolError("Resultado exitoso con error contradictorio.")
        return
    if path is not None:
        raise DialogProtocolError("Resultado no exitoso con ruta contradictoria.")
    if status == STATUS_CANCELLED:
        if error_code is not None:
            raise DialogProtocolError("Cancelacion con error contradictorio.")
        return
    if not isinstance(error_code, str) or not error_code:
        raise DialogProtocolError("Resultado tecnico sin codigo de error.")


def write_result(
    request_id: object,
    *,
    status: str,
    path: Optional[str] = None,
    error_code: Optional[str] = None,
    dialog_dir: Optional[Path] = None,
) -> Path:
    validated_id = validate_request_id(request_id)
    payload = {
        "schema": PROTOCOL_SCHEMA,
        "request_id": validated_id,
        "status": status,
        "path": path,
        "error_code": error_code,
    }
    _validate_result_payload(payload, validated_id)
    destination = result_path(validated_id, dialog_dir=dialog_dir)
    _write_json_atomic(destination, payload)
    return destination


def read_result(request_id: object, *, dialog_dir: Optional[Path] = None) -> dict[str, Any]:
    validated_id = validate_request_id(request_id)
    payload = _read_json_object(result_path(validated_id, dialog_dir=dialog_dir))
    _validate_result_payload(payload, validated_id)
    return payload


def remove_exchange_files(request_id: object, *, dialog_dir: Optional[Path] = None) -> None:
    """Elimina solo los dos archivos derivados del identificador validado."""
    for path in (
        request_path(request_id, dialog_dir=dialog_dir),
        result_path(request_id, dialog_dir=dialog_dir),
    ):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def cleanup_stale_dialog_ipc(
    *,
    dialog_dir: Optional[Path] = None,
    ttl_seconds: float = DIALOG_IPC_TTL_SECONDS,
    now: Optional[float] = None,
) -> int:
    """Elimina residuos propios antiguos sin recorrer ni seguir enlaces.

    El barrido es deliberadamente cerrado: solo reconoce los nombres exactos
    que generan ``request_path``/``result_path`` y ``_write_json_atomic``.
    Cualquier error de inspeccion o borrado es best-effort y no bloquea el
    arranque normal de TZ Analyzer.
    """
    removed = 0

    # Para el barrido no se usa ``resolve``: cada componente propio bajo el
    # ancla permitida se inspecciona literalmente. Ante duda se conserva.
    anchor, base = _dialog_cleanup_location(dialog_dir)
    if not _safe_cleanup_directory(anchor, base):
        return removed

    current_time = time.time() if now is None else now
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    try:
        with os.scandir(base) as entries:
            for entry in entries:
                exchange_match = _STALE_EXCHANGE_RE.fullmatch(entry.name)
                temporary_match = _STALE_TEMPORARY_RE.fullmatch(entry.name)
                if exchange_match is None and temporary_match is None:
                    continue
                try:
                    metadata = entry.stat(follow_symlinks=False)
                    if not stat.S_ISREG(metadata.st_mode):
                        continue
                    if getattr(metadata, "st_file_attributes", 0) & reparse_flag:
                        continue
                    if current_time - metadata.st_mtime <= ttl_seconds:
                        continue
                    if exchange_match is not None:
                        # Los finales atomicos deben conservar el schema e ID
                        # que declara su nombre. Un archivo solo parecido se
                        # deja intacto, aun si es antiguo.
                        try:
                            payload = _read_json_object(Path(entry.path))
                        except DialogProtocolError:
                            continue
                        if payload.get("schema") != PROTOCOL_SCHEMA:
                            continue
                        if payload.get("request_id") != exchange_match.group("request_id"):
                            continue
                    os.unlink(entry.path)
                    removed += 1
                except OSError:
                    continue
    except OSError:
        return removed

    return removed
