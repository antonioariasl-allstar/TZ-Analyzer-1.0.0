"""tz_web.machine_id — identidad técnica estable y no sensible del equipo.

Un UUID aleatorio persistido bajo ``%LOCALAPPDATA%\\TZ Analyzer`` (misma
carpeta que ``tz_core.user_paths`` ya usa para config de usuario), generado
una única vez. No deriva de hostname, usuario, MAC ni ningún otro dato de
hardware/identidad real — sirve solo para que un futuro housekeeping
(MB8-B2) pueda distinguir stagings del mismo equipo entre sí, nunca para
identificar a la persona o la máquina.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

from tz_core.user_paths import get_user_config_dir

_LOGGER = logging.getLogger("tz_web.machine_id")

_MACHINE_ID_FILENAME = "machine_id"


def _machine_id_path(localappdata: Optional[str] = None) -> str:
    return str(get_user_config_dir(localappdata) / _MACHINE_ID_FILENAME)


def _is_valid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def get_or_create_machine_id(localappdata: Optional[str] = None) -> Optional[str]:
    """Identificador técnico persistente de esta instalación.

    Primera lectura: si no existe, genera un UUID4 y lo persiste. Lecturas
    siguientes devuelven siempre el mismo valor. Si el archivo existe pero su
    contenido no es un UUID válido, no se sobrescribe (conducta
    conservadora): se devuelve ``None`` en vez de arriesgar una identidad
    duplicada silenciosa.
    """
    path = _machine_id_path(localappdata)
    try:
        with open(path, "r", encoding="utf-8") as source:
            existing = source.read().strip()
        if _is_valid(existing):
            return existing
        _LOGGER.warning("machine_id existente no tiene el formato esperado; no se sobrescribe.")
        return None
    except FileNotFoundError:
        pass
    except OSError:
        _LOGGER.warning("no se pudo leer machine_id.")
        return None

    new_id = str(uuid.uuid4())
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, new_id.encode("utf-8"))
        finally:
            os.close(fd)
        return new_id
    except FileExistsError:
        # Carrera: otro proceso lo creó entre nuestra lectura y esta escritura.
        try:
            with open(path, "r", encoding="utf-8") as source:
                existing = source.read().strip()
            if _is_valid(existing):
                return existing
        except OSError:
            pass
        return None
    except OSError:
        _LOGGER.warning("no se pudo persistir machine_id.")
        return None
