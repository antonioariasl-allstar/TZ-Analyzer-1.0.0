"""tz_web.instance — instancia unica del backend local (MICROBLOQUE 5).

Resuelve AUD-02 (instancia unica/puerto): un bloqueo exclusivo a nivel de
sistema operativo (no un archivo de lock "a mano") decide quien es la
instancia dueña del proceso, y metadata local por usuario permite a un
segundo lanzamiento encontrar y validar esa instancia sin escanear puertos
ni confiar en el PID.

Por que un lock de SO y no un archivo con PID:
- ``msvcrt.locking()`` ata el bloqueo al *handle* abierto del proceso, no a
  un valor escrito en disco. Si el proceso muere (incluso por crash), el
  sistema operativo libera el bloqueo automaticamente al cerrar el handle.
  El siguiente lanzamiento simplemente vuelve a poder adquirirlo — no hace
  falta inspeccionar PID, edad de archivo ni "limpiar" nada a mano.
- Un PID reciclado por el sistema operativo nunca puede confundirse con una
  instancia viva: el lock por handle no depende del valor del PID en
  absoluto.

Ver docs/LAUNCHER_LIFECYCLE.md para el diseño completo.
"""

from __future__ import annotations

import json
import logging
import msvcrt
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from tz_core.user_paths import get_user_config_dir

INSTANCE_SCHEMA_VERSION = 1
LAUNCHER_VERSION = "1.0"

_RUN_DIR_NAME = "run"
_LOCK_FILENAME = "instance.lock"
_METADATA_FILENAME = "instance.json"

HEALTH_TIMEOUT_SECONDS = 1.5

_LOGGER = logging.getLogger("tz_web.instance")


def get_run_dir(localappdata: Optional[str] = None) -> Path:
    """Carpeta local por usuario para lock/metadata de instancia.

    Nunca dentro del repositorio ni de Program Files (AUD-14, no resuelto
    por completo aqui, pero esta ubicacion ya cumple esa restriccion): usa
    el mismo directorio de usuario que ``tz_core.user_paths`` ya usa para
    config editable (``%LOCALAPPDATA%\\TZ Analyzer``), en una subcarpeta
    propia para no mezclar archivos de vida corta con config persistente.
    """
    run_dir = get_user_config_dir(localappdata) / _RUN_DIR_NAME
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


@dataclass(frozen=True)
class InstanceMetadata:
    schema_version: int
    instance_id: str
    pid: int
    port: int
    token: str
    created_at: float
    app_version: str
    launcher_version: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstanceMetadata":
        return cls(
            schema_version=int(data["schema_version"]),
            instance_id=str(data["instance_id"]),
            pid=int(data["pid"]),
            port=int(data["port"]),
            token=str(data["token"]),
            created_at=float(data["created_at"]),
            app_version=str(data.get("app_version") or ""),
            launcher_version=str(data.get("launcher_version") or ""),
        )

    def log_safe_dict(self) -> Dict[str, Any]:
        """Version para logs: nunca el token completo (sección K)."""
        data = self.to_dict()
        data["token"] = (self.token[:6] + "…") if self.token else ""
        return data


class InstanceLock:
    """Bloqueo exclusivo de instancia atado al ciclo de vida del proceso.

    ``try_acquire()`` adquiere un lock de SO no bloqueante sobre un archivo
    fijo en ``run_dir``. Si el proceso que lo sostiene termina — de forma
    limpia o por crash — el sistema operativo libera el lock al cerrar el
    handle; no depende de que nadie borre el archivo.
    """

    def __init__(self, run_dir: Path):
        self._lock_path = run_dir / _LOCK_FILENAME
        self._metadata_path = run_dir / _METADATA_FILENAME
        self._fd: Optional[int] = None

    @property
    def metadata_path(self) -> Path:
        return self._metadata_path

    def try_acquire(self) -> bool:
        if self._fd is not None:
            return True
        fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            if os.fstat(fd).st_size < 1:
                os.write(fd, b"\0")
                os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def write_metadata(self, metadata: InstanceMetadata) -> None:
        if self._fd is None:
            raise RuntimeError("No se puede escribir metadata sin sostener el lock de instancia.")
        tmp_path = self._metadata_path.with_name(self._metadata_path.name + ".tmp")
        tmp_path.write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, self._metadata_path)

    def read_metadata(self) -> Optional[InstanceMetadata]:
        try:
            raw = self._metadata_path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            return InstanceMetadata.from_dict(json.loads(raw))
        except (ValueError, KeyError, TypeError):
            return None

    def release(self) -> None:
        """Cierre limpio: invalida solo la metadata propia (el lock ya
        garantiza que, mientras estuvo sostenido, nadie mas pudo escribirla)
        y libera el handle — el sistema operativo hace el resto."""
        if self._fd is None:
            return
        try:
            try:
                self._metadata_path.unlink()
            except OSError:
                pass
            try:
                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        finally:
            os.close(self._fd)
            self._fd = None


_current_instance_id: Optional[str] = None


def set_current_instance_id(instance_id: Optional[str]) -> None:
    """Registra el ``instance_id`` de esta ejecución para consumidores sin
    contexto Flask propio (p. ej. ``tz_web.output_transaction``, que corre en
    threads de trabajo sin app context). Único punto de entrada: llamado por
    ``tz_web.app.create_app()`` con el mismo valor que ya recibe la app."""
    global _current_instance_id
    _current_instance_id = instance_id


def get_current_instance_id() -> Optional[str]:
    return _current_instance_id


def check_health(
    port: int, token: str, timeout: float = HEALTH_TIMEOUT_SECONDS
) -> Optional[Dict[str, Any]]:
    """Valida una instancia existente vía su ``/internal/health`` autenticado.

    Devuelve el cuerpo JSON si respondio 200 con un cuerpo interpretable;
    ``None`` en cualquier otro caso (puerto libre/ajeno, timeout, proceso
    muerto, respuesta invalida) — el llamador no distingue estos casos entre
    si porque, para la decision de arranque, todos significan lo mismo: la
    instancia referenciada por la metadata no puede validarse.
    """
    url = f"http://127.0.0.1:{port}/internal/health"
    request = Request(url, headers={"X-TZ-Token": token})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            body = response.read().decode("utf-8")
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except (URLError, OSError, ValueError, TimeoutError):
        return None


@dataclass(frozen=True)
class StartupPlan:
    action: str  # "start" | "reuse" | "blocked"
    metadata: Optional[InstanceMetadata]
    reason: Optional[str] = None


def resolve_startup_plan(
    lock: InstanceLock,
    *,
    health_checker: Callable[[int, str], Optional[Dict[str, Any]]] = check_health,
    retries: int = 3,
    retry_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> StartupPlan:
    """Decide si este lanzamiento arranca, reutiliza o queda bloqueado.

    Funcion pura respecto de I/O real (``lock``/``health_checker``/``sleep``
    son inyectables) para poder probar cada rama sin procesos ni red reales.

    - ``lock.try_acquire()`` exitoso: nadie mas sostiene el lock ahora mismo
      (ya sea porque no habia nadie, o porque el dueño anterior crasheo y el
      SO libero el handle) -> "start", esta llamada es la nueva instancia.
    - Lock ocupado: se reintenta el health autenticado unas pocas veces
      (una instancia real puede tardar un instante en levantar su propio
      servidor tras adquirir el lock) contra el puerto/token de la metadata
      existente. Si coincide el ``instance_id`` -> "reuse". Si nunca
      responde valido -> "blocked" (nunca se fuerza el lock, ni se escanean
      otros puertos, ni se asume que el PID de la metadata sigue vivo).
    """
    if lock.try_acquire():
        return StartupPlan(action="start", metadata=None)

    metadata = lock.read_metadata()
    if metadata is None:
        return StartupPlan(action="blocked", metadata=None, reason="metadata_unreadable")

    last_health: Optional[Dict[str, Any]] = None
    for attempt in range(retries):
        if attempt:
            sleep(retry_delay)
        last_health = health_checker(metadata.port, metadata.token)
        if last_health is not None and last_health.get("instance_id") == metadata.instance_id:
            return StartupPlan(action="reuse", metadata=metadata)

    reason = "stale_or_foreign" if last_health is None else "instance_id_mismatch"
    return StartupPlan(action="blocked", metadata=metadata, reason=reason)
