"""Selector nativo de carpeta en un proceso hijo controlado.

En desarrollo reinvoca ``python tz_launcher.py``. En una build frozen
reinvoca el mismo ejecutable. El hijo se registra en memoria y el hilo que
lo posee puede terminarlo por timeout o cuando lifecycle deja ``RUNNING``.
"""

from __future__ import annotations

import secrets
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from tz_core.user_paths import is_frozen
from tz_folder_dialog_ipc import (
    INTERNAL_MODE_ARGUMENT,
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_SUCCESS,
    STATUS_UNAVAILABLE,
    DialogProtocolError,
    read_result,
    remove_exchange_files,
    write_request,
)

_LAUNCHER_SCRIPT_NAME = "tz_launcher.py"
DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_POLL_INTERVAL_SECONDS = 0.05
DEFAULT_TERMINATE_GRACE_SECONDS = 1.0
DEFAULT_KILL_GRACE_SECONDS = 1.0


class FolderDialogUnavailableError(RuntimeError):
    """El selector no pudo iniciarse o producir un resultado valido."""


class FolderDialogTimeoutError(FolderDialogUnavailableError):
    """El hijo excedio el plazo y fue terminado."""


class FolderDialogInterruptedError(FolderDialogUnavailableError):
    """Lifecycle abandono RUNNING mientras el selector estaba abierto."""


class FolderDialogBusyError(FolderDialogUnavailableError):
    """El registro conserva otro selector que todavia puede estar vivo."""


class _DialogChildRegistryClosedError(RuntimeError):
    """El proceso padre ya inicio su cierre y no acepta nuevos hijos."""


class _DialogChildAlreadyRunningError(RuntimeError):
    """El registro no admite solapar dos procesos de selector."""


@dataclass(eq=False)
class DialogChildHandle:
    """Referencia tecnica; nunca guarda rutas elegidas ni datos del caso."""

    process: Any
    request_id: str
    dialog_dir: Optional[Path]
    operation_lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
    )


class DialogChildRegistry:
    """Registro thread-safe de procesos de selector pertenecientes al padre.

    El lock global solo protege la coleccion. Nunca se mantiene durante
    ``wait`` ni durante filesystem. Cada handle serializa poll/wait/terminate
    para que finalizacion natural, timeout y shutdown puedan competir sin
    terminar dos veces el mismo proceso.
    """

    def __init__(
        self,
        *,
        terminate_grace: float = DEFAULT_TERMINATE_GRACE_SECONDS,
        kill_grace: float = DEFAULT_KILL_GRACE_SECONDS,
    ) -> None:
        self._lock = threading.Lock()
        self._children: dict[int, DialogChildHandle] = {}
        self._accepting = True
        self._terminate_grace = terminate_grace
        self._kill_grace = kill_grace

    def spawn(
        self,
        popen_factory: Callable[..., Any],
        cmd: list[str],
        *,
        request_id: str,
        dialog_dir: Optional[Path],
        popen_kwargs: dict[str, Any],
    ) -> DialogChildHandle:
        """Crea y registra bajo una sola seccion critica, sin ventana ciega."""
        with self._lock:
            if not self._accepting:
                raise _DialogChildRegistryClosedError(
                    "El registro de selectores ya esta cerrando."
                )
            # La ruta HTTP aporta el rechazo rapido habitual, pero el registro
            # es la ultima barrera: si Windows no confirmo ni terminate ni
            # kill, el handle se conserva y nunca se solapa un segundo hijo.
            if self._children:
                raise _DialogChildAlreadyRunningError(
                    "El registro conserva un selector activo."
                )
            process = popen_factory(cmd, **popen_kwargs)
            handle = DialogChildHandle(
                process=process,
                request_id=request_id,
                dialog_dir=Path(dialog_dir) if dialog_dir is not None else None,
            )
            self._children[id(handle)] = handle
            return handle

    def poll(self, handle: DialogChildHandle) -> Optional[int]:
        with handle.operation_lock:
            return self._poll_process(handle.process)

    @staticmethod
    def _poll_process(process: Any) -> Optional[int]:
        """Un fallo del SO nunca equivale a confirmar que el hijo murio."""
        try:
            return process.poll()
        except (OSError, subprocess.SubprocessError):
            return None

    def wait(self, handle: DialogChildHandle, *, timeout: float) -> int:
        with handle.operation_lock:
            return int(handle.process.wait(timeout=timeout))

    def discard(self, handle: DialogChildHandle) -> None:
        with self._lock:
            self._children.pop(id(handle), None)

    def terminate(self, handle: DialogChildHandle) -> bool:
        """Termina con gracia y escala a kill; nunca espera indefinidamente."""
        stopped = False
        with handle.operation_lock:
            process = handle.process
            if self._poll_process(process) is not None:
                stopped = True
            else:
                try:
                    process.terminate()
                except (OSError, subprocess.SubprocessError):
                    pass
                try:
                    process.wait(timeout=self._terminate_grace)
                    stopped = True
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except (OSError, subprocess.SubprocessError):
                        pass
                    try:
                        process.wait(timeout=self._kill_grace)
                        stopped = True
                    except subprocess.TimeoutExpired:
                        stopped = self._poll_process(process) is not None
                    except (OSError, subprocess.SubprocessError):
                        stopped = self._poll_process(process) is not None
                except (OSError, subprocess.SubprocessError):
                    stopped = self._poll_process(process) is not None

        if stopped:
            self.discard(handle)
        return stopped

    def snapshot(self) -> tuple[DialogChildHandle, ...]:
        with self._lock:
            return tuple(self._children.values())

    def has_live_child(self) -> bool:
        live = False
        for handle in self.snapshot():
            if self.poll(handle) is None:
                live = True
            else:
                self.discard(handle)
        return live

    def terminate_all(self) -> tuple[DialogChildHandle, ...]:
        """Cierra hijos y devuelve los que el SO no confirmo como muertos."""
        # Cerrar la compuerta y tomar el snapshot es atomico respecto a spawn:
        # ningun Popen puede aparecer despues del snapshot de shutdown.
        with self._lock:
            self._accepting = False
            handles = tuple(self._children.values())
        survivors = []
        for handle in handles:
            stopped = self.terminate(handle)
            if not stopped:
                # No borrar el request/result de un hijo aun vivo: podria
                # recrear el resultado despues y aparentar una limpieza que
                # el padre no pudo garantizar. El TTL lo tratara en otro
                # arranque, cuando ya sea seguro inspeccionarlo.
                survivors.append(handle)
                continue
            try:
                remove_exchange_files(handle.request_id, dialog_dir=handle.dialog_dir)
            except (DialogProtocolError, OSError):
                pass
        return tuple(survivors)


DIALOG_CHILD_REGISTRY = DialogChildRegistry()


def has_live_dialog_child() -> bool:
    return DIALOG_CHILD_REGISTRY.has_live_child()


def shutdown_dialog_children() -> tuple[DialogChildHandle, ...]:
    return DIALOG_CHILD_REGISTRY.terminate_all()


def _default_launcher_script() -> Path:
    return Path(__file__).resolve().parent.parent / _LAUNCHER_SCRIPT_NAME


def _new_request_id() -> str:
    return secrets.token_hex(32)


def _never_cancel() -> bool:
    return False


def _cancellation_requested(callback: Callable[[], bool]) -> bool:
    try:
        return bool(callback())
    except Exception:  # noqa: BLE001 - fallo del control implica cierre seguro
        return True


def pick_folder(
    *,
    initial_dir: Optional[str] = None,
    title: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    launcher_script: Optional[Path] = None,
    dialog_dir: Optional[Path] = None,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    is_frozen_fn: Callable[[], bool] = is_frozen,
    request_id_factory: Callable[[], str] = _new_request_id,
    cancel_requested: Callable[[], bool] = _never_cancel,
    child_registry: DialogChildRegistry = DIALOG_CHILD_REGISTRY,
    monotonic_fn: Callable[[], float] = time.monotonic,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> Optional[str]:
    """Abre el selector; devuelve una ruta existente o ``None`` al cancelar."""
    request_id = request_id_factory()
    frozen = is_frozen_fn()

    if frozen:
        cmd = [sys.executable, INTERNAL_MODE_ARGUMENT, request_id]
    else:
        script = launcher_script if launcher_script is not None else _default_launcher_script()
        if not Path(script).is_file():
            raise FolderDialogUnavailableError(
                "No se encontro el entrypoint de TZ Analyzer para abrir el selector."
            )
        cmd = [sys.executable, str(script), INTERNAL_MODE_ARGUMENT, request_id]

    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "shell": False,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    handle: Optional[DialogChildHandle] = None
    completed_code: Optional[int] = None
    try:
        if _cancellation_requested(cancel_requested):
            raise FolderDialogInterruptedError(
                "El selector se cerro porque TZ Analyzer esta cerrando."
            )

        write_request(
            request_id,
            title=title,
            initial_dir=initial_dir,
            dialog_dir=dialog_dir,
        )
        try:
            handle = child_registry.spawn(
                popen_factory,
                cmd,
                request_id=request_id,
                dialog_dir=dialog_dir,
                popen_kwargs=popen_kwargs,
            )
        except _DialogChildRegistryClosedError as exc:
            raise FolderDialogInterruptedError(
                "El selector se cerro porque TZ Analyzer esta cerrando."
            ) from exc
        except _DialogChildAlreadyRunningError as exc:
            raise FolderDialogBusyError(
                "Ya existe un selector de carpeta abierto."
            ) from exc
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise FolderDialogUnavailableError(
                "No se pudo iniciar el selector de carpetas."
            ) from exc

        deadline = monotonic_fn() + timeout
        while True:
            if _cancellation_requested(cancel_requested):
                child_registry.terminate(handle)
                raise FolderDialogInterruptedError(
                    "El selector se interrumpio porque TZ Analyzer esta cerrando."
                )

            completed_code = child_registry.poll(handle)
            if completed_code is not None:
                break

            remaining = deadline - monotonic_fn()
            if remaining <= 0:
                stopped = child_registry.terminate(handle)
                suffix = (
                    " y fue cerrado."
                    if stopped
                    else "; no se pudo confirmar el cierre del proceso interno."
                )
                raise FolderDialogTimeoutError(
                    f"El selector de carpetas excedio el plazo de {timeout:g} segundos{suffix}"
                )

            try:
                completed_code = child_registry.wait(
                    handle,
                    timeout=min(max(poll_interval, 0.001), remaining),
                )
                break
            except subprocess.TimeoutExpired:
                continue

        try:
            result = read_result(request_id, dialog_dir=dialog_dir)
        except DialogProtocolError as exc:
            secondary = (
                f" (codigo interno {completed_code})"
                if isinstance(completed_code, int)
                else ""
            )
            raise FolderDialogUnavailableError(
                f"El selector no produjo un resultado estructurado valido{secondary}."
            ) from exc

        status = result["status"]
        if status == STATUS_CANCELLED:
            return None
        if status == STATUS_UNAVAILABLE:
            raise FolderDialogUnavailableError(
                "El selector nativo no esta disponible en este entorno grafico."
            )
        if status == STATUS_ERROR:
            raise FolderDialogUnavailableError(
                "El selector de carpetas termino con un error tecnico controlado."
            )
        if status != STATUS_SUCCESS:
            raise FolderDialogUnavailableError("Estado inesperado del selector de carpetas.")

        selected = Path(result["path"])
        if not selected.exists() or not selected.is_dir():
            raise FolderDialogUnavailableError(
                "El selector devolvio una carpeta que ya no existe o no es valida."
            )
        return str(result["path"])
    except (DialogProtocolError, OSError) as exc:
        raise FolderDialogUnavailableError(
            "No se pudo preparar el intercambio tecnico del selector de carpetas."
        ) from exc
    finally:
        safe_to_remove_ipc = handle is None
        if handle is not None:
            try:
                if child_registry.poll(handle) is None:
                    safe_to_remove_ipc = child_registry.terminate(handle)
                else:
                    child_registry.discard(handle)
                    safe_to_remove_ipc = True
            except (OSError, subprocess.SubprocessError):
                safe_to_remove_ipc = False
        if safe_to_remove_ipc:
            try:
                remove_exchange_files(request_id, dialog_dir=dialog_dir)
            except (DialogProtocolError, OSError):
                pass
