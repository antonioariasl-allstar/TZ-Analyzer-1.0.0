"""Publicación transaccional y trazabilidad de salidas de TZ Analyzer web.

La generación ocurre dentro de un directorio marcado situado en el mismo
volumen que el destino. Solo un conjunto validado y con manifiesto cerrado se
renombra a su carpeta visible final. El manifiesto es la única fuente final
de hashes; nunca se incluye a sí mismo y el log de ejecución queda fuera del
conjunto por contrato (best-effort, opción B).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence
from xml.etree import ElementTree


RESULT_SUCCESS = "success"
RESULT_PARTIAL = "partial"
RESULT_FAILED = "failed"
MANIFEST_SCHEMA = "TZ_ANALYZER_MANIFEST_V1"


class TransactionError(RuntimeError):
    """Error base del contrato transaccional."""


class InputIntegrityError(TransactionError):
    """Los bytes de entrada no corresponden al digest aceptado."""


class OutputValidationError(TransactionError):
    """Un producto obligatorio o su integridad no son verificables."""


class OutputCollisionError(TransactionError):
    """La publicación encontraría una carpeta final ya existente."""


@dataclass(frozen=True)
class InputSnapshot:
    path: str
    sha256: str
    original_name: str


@dataclass(frozen=True)
class ArtifactSpec:
    """Producto conocido que participa en la matriz de resultado.

    ``required`` determina fallo terminal. Un producto no obligatorio con
    ``requested=True`` que falta o es inválido degrada a PARTIAL. Los archivos
    regulares adicionales bajo ``work_dir`` se incorporan como ``support`` sin
    afectar por ausencia el estado.
    """

    role: str
    path: Optional[str]
    required: bool
    requested: bool = True


@dataclass(frozen=True)
class ManifestEntry:
    role: str
    relative_path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class PublicationResult:
    status: str
    final_dir: str
    artifacts: Dict[str, str]
    manifest_path: str
    entries: Sequence[ManifestEntry]
    warnings: Sequence[str] = field(default_factory=tuple)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_input_snapshot(
    source_path: str,
    snapshot_dir: str,
    *,
    expected_sha256: str,
    original_name: Optional[str] = None,
) -> InputSnapshot:
    """Copia los bytes aceptados a una ruta exclusiva y verifica ambos lados.

    Se hashea el origen antes y después de copiar. Esto detecta tanto un cambio
    previo como una escritura concurrente durante la copia. El snapshot se
    conserva dentro del directorio de la sesión hasta descartar el caso.
    """
    source_abs = os.path.abspath(source_path)
    expected = (expected_sha256 or "").strip().lower()
    if len(expected) != 64:
        raise InputIntegrityError("El SHA-256 aceptado de la entrada no es válido.")
    if not os.path.isfile(source_abs):
        raise InputIntegrityError("El archivo aceptado ya no está disponible.")

    before = sha256_file(source_abs)
    if before != expected:
        raise InputIntegrityError("El archivo de entrada cambió después de ser aceptado.")

    os.makedirs(snapshot_dir, exist_ok=True)
    extension = os.path.splitext(source_abs)[1].lower() or ".bin"
    snapshot_path = os.path.join(snapshot_dir, f".execution-input-{uuid.uuid4().hex}{extension}")
    try:
        with open(source_abs, "rb") as source, open(snapshot_path, "xb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
        snapshot_digest = sha256_file(snapshot_path)
        after = sha256_file(source_abs)
        if before != after or snapshot_digest != expected:
            raise InputIntegrityError(
                "No se pudo obtener un snapshot estable de los bytes aceptados."
            )
    except Exception:
        try:
            os.remove(snapshot_path)
        except OSError:
            pass
        raise

    return InputSnapshot(
        path=snapshot_path,
        sha256=snapshot_digest,
        original_name=os.path.basename(original_name or source_abs),
    )


def verify_input_snapshot(snapshot_path: str, expected_sha256: str) -> None:
    if not snapshot_path or not os.path.isfile(snapshot_path):
        raise InputIntegrityError("El snapshot de entrada ya no está disponible.")
    actual = sha256_file(snapshot_path)
    if actual != (expected_sha256 or "").strip().lower():
        raise InputIntegrityError("El snapshot de entrada cambió durante el procesamiento.")


@dataclass
class OutputTransaction:
    base_dir: str
    name: str
    reservation_dir: str
    staging_root: str
    work_dir: str
    final_dir: str
    _published: bool = False

    @classmethod
    def reserve(cls, base_dir: str, candidate: str) -> "OutputTransaction":
        """Reserva cooperativamente un nombre sin crear una carpeta final normal."""
        base_abs = os.path.abspath(base_dir)
        os.makedirs(base_abs, exist_ok=True)
        clean_candidate = os.path.basename(candidate.strip())
        if not clean_candidate or clean_candidate in (".", ".."):
            raise OutputCollisionError("El nombre de salida no es válido.")

        attempt = 1
        while True:
            name = clean_candidate if attempt == 1 else f"{clean_candidate}_{attempt:02d}"
            final_dir = os.path.join(base_abs, name)
            # La propia carpeta de trabajo marcada es también la reserva
            # cooperativa. Evita duplicar el nombre/ruta y reduce longitud en
            # Windows; solo adquiere el nombre final mediante el rename.
            reservation_dir = os.path.join(base_abs, f".{name}.tzp")
            if os.path.exists(final_dir):
                attempt += 1
                continue
            try:
                os.mkdir(reservation_dir)
            except FileExistsError:
                attempt += 1
                continue

            # Un proceso ajeno puede haber creado el destino entre el primer
            # check y nuestra reserva. No se sobrescribe: se libera y reintenta.
            if os.path.exists(final_dir):
                os.rmdir(reservation_dir)
                attempt += 1
                continue

            staging_root = reservation_dir
            work_dir = reservation_dir
            return cls(
                base_dir=base_abs,
                name=name,
                reservation_dir=reservation_dir,
                staging_root=staging_root,
                work_dir=work_dir,
                final_dir=final_dir,
            )

    def publish(self) -> str:
        """Renombra el caso validado sin overwrite y conserva la reserva hasta el final."""
        if self._published:
            return self.final_dir
        if os.path.exists(self.final_dir):
            raise OutputCollisionError(
                f"La carpeta final ya existe y no se sobrescribirá: {self.name}"
            )
        try:
            os.rename(self.work_dir, self.final_dir)
            self._published = True
            return self.final_dir
        finally:
            if self._published:
                try:
                    os.rmdir(self.reservation_dir)
                except OSError:
                    pass

    def abort(self) -> None:
        """Política de fallo: elimina staging y reserva; nunca deja final normal."""
        if self._published and os.path.isdir(self.final_dir):
            failed_hidden = os.path.join(
                self.base_dir, f".{self.name}.failed-{uuid.uuid4().hex}"
            )
            try:
                os.rename(self.final_dir, failed_hidden)
                shutil.rmtree(failed_hidden, ignore_errors=True)
            except OSError:
                # Solo se elimina una carpeta que esta transacción publicó y
                # mantiene reservada; nunca un destino preexistente.
                shutil.rmtree(self.final_dir, ignore_errors=True)
            self._published = False
        shutil.rmtree(self.staging_root, ignore_errors=True)
        try:
            os.rmdir(self.reservation_dir)
        except OSError:
            pass


def _relative_to_work(path: str, work_dir: str) -> str:
    path_abs = os.path.abspath(path)
    work_abs = os.path.abspath(work_dir)
    try:
        relative = os.path.relpath(path_abs, work_abs)
    except ValueError as exc:
        raise OutputValidationError("Un artefacto está fuera del staging transaccional.") from exc
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        raise OutputValidationError("Un artefacto está fuera del staging transaccional.")
    return Path(relative).as_posix()


def _validate_regular_file(path: str) -> None:
    if not os.path.isfile(path):
        raise OutputValidationError("El producto no existe como archivo regular.")
    if os.path.getsize(path) <= 0:
        raise OutputValidationError("El producto está vacío.")


def _validate_artifact(role: str, path: str) -> None:
    _validate_regular_file(path)
    if role == "html":
        try:
            with open(path, "r", encoding="utf-8") as source:
                if not source.read():
                    raise OutputValidationError("El HTML está vacío.")
        except UnicodeDecodeError as exc:
            raise OutputValidationError("El HTML no es UTF-8 legible.") from exc
    elif role == "kmz":
        try:
            with zipfile.ZipFile(path, "r") as archive:
                names = archive.namelist()
                if not names or archive.testzip() is not None:
                    raise OutputValidationError("El KMZ está corrupto.")
                kml_names = [name for name in names if name.lower().endswith(".kml")]
                if not kml_names:
                    raise OutputValidationError("El KMZ no contiene un KML.")
                for kml_name in kml_names:
                    try:
                        root = ElementTree.fromstring(archive.read(kml_name))
                    except (KeyError, ElementTree.ParseError) as exc:
                        raise OutputValidationError(
                            f"El KMZ contiene un KML inválido: {kml_name}."
                        ) from exc
                    if root.tag.rsplit("}", 1)[-1].lower() != "kml":
                        raise OutputValidationError(
                            f"El XML dentro del KMZ no tiene raíz KML: {kml_name}."
                        )
        except (OSError, zipfile.BadZipFile) as exc:
            raise OutputValidationError("El KMZ no es un ZIP legible.") from exc
    elif role == "kml":
        try:
            root = ElementTree.parse(path).getroot()
        except (OSError, ElementTree.ParseError) as exc:
            raise OutputValidationError("El KML no es XML válido.") from exc
        if root.tag.rsplit("}", 1)[-1].lower() != "kml":
            raise OutputValidationError("El XML no tiene un elemento raíz KML.")
    elif role == "snapshot_json":
        try:
            with open(path, "r", encoding="utf-8") as source:
                json.load(source)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OutputValidationError("El snapshot JSON no es válido.") from exc


def _write_manifest(
    path: str,
    *,
    mode: str,
    final_status: str,
    executed_at: str,
    input_metadata: Optional[Mapping[str, Any]],
    entries: Sequence[ManifestEntry],
    unhashed_files: Sequence[str],
) -> None:
    metadata: Dict[str, Any] = {
        "algorithm": "SHA-256",
        "executed_at": executed_at,
        "log_policy": "best-effort-excluded",
        "mode": str(mode),
        "schema": MANIFEST_SCHEMA,
        "status": final_status.upper(),
        "unhashed_files": list(unhashed_files),
    }
    if input_metadata:
        metadata["input"] = dict(input_metadata)

    with open(path, "x", encoding="utf-8", newline="\n") as manifest:
        manifest.write(MANIFEST_SCHEMA + "\n")
        manifest.write(
            "METADATA\t"
            + json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        )
        for entry in entries:
            manifest.write(
                f"SHA256\t{entry.sha256}\t{entry.size}\t{entry.role}\t{entry.relative_path}\n"
            )


def _discover_files(work_dir: str) -> Iterable[str]:
    for root, dirs, files in os.walk(work_dir):
        dirs.sort()
        files.sort()
        for filename in files:
            path = os.path.join(root, filename)
            if os.path.isfile(path):
                yield path


def finalize_output(
    transaction: OutputTransaction,
    *,
    artifacts: Sequence[ArtifactSpec],
    mode: str,
    manifest_name: str,
    input_metadata: Optional[Mapping[str, Any]] = None,
    executed_at: Optional[str] = None,
    excluded_paths: Sequence[str] = (),
    pre_publish_check: Optional[Callable[[], None]] = None,
) -> PublicationResult:
    """Valida, manifiesta y publica; cualquier fallo aborta la transacción."""
    manifest_path = os.path.join(transaction.work_dir, os.path.basename(manifest_name))
    excluded_abs = {os.path.abspath(path) for path in excluded_paths if path}
    excluded_abs.add(os.path.abspath(manifest_path))
    warnings: list[str] = []
    explicit_roles: Dict[str, str] = {}
    role_by_abs: Dict[str, str] = {}
    partial = False

    try:
        unhashed_files: list[str] = []
        for excluded in sorted(excluded_abs):
            if excluded == os.path.abspath(manifest_path):
                continue
            # Toda exclusión declarada también debe pertenecer al staging;
            # el manifiesto solo registra rutas relativas.
            relative = _relative_to_work(excluded, transaction.work_dir)
            if os.path.isfile(excluded):
                unhashed_files.append(relative)

        for spec in artifacts:
            path = os.path.abspath(spec.path) if spec.path else None
            if path is None or not os.path.isfile(path):
                if spec.required:
                    raise OutputValidationError(
                        f"Falta el producto obligatorio: {spec.role}."
                    )
                if spec.requested:
                    partial = True
                    warnings.append(f"No se generó el producto opcional solicitado: {spec.role}.")
                continue

            _relative_to_work(path, transaction.work_dir)
            try:
                _validate_artifact(spec.role, path)
            except OutputValidationError as exc:
                if spec.required:
                    raise OutputValidationError(
                        f"Producto obligatorio inválido ({spec.role}): {exc}"
                    ) from exc
                try:
                    os.remove(path)
                except OSError as remove_exc:
                    raise OutputValidationError(
                        f"No se pudo retirar el producto opcional inválido ({spec.role})."
                    ) from remove_exc
                if os.path.exists(path):
                    raise OutputValidationError(
                        f"El producto opcional inválido sigue presente ({spec.role})."
                    )
                if spec.requested:
                    partial = True
                    warnings.append(f"Producto opcional inválido ({spec.role}): {exc}")
                continue
            explicit_roles[spec.role] = path
            role_by_abs[path] = spec.role

        status = RESULT_PARTIAL if partial else RESULT_SUCCESS
        entries: list[ManifestEntry] = []
        for path in _discover_files(transaction.work_dir):
            path_abs = os.path.abspath(path)
            if path_abs in excluded_abs:
                continue
            relative = _relative_to_work(path_abs, transaction.work_dir)
            role = role_by_abs.get(path_abs, "support")
            entries.append(
                ManifestEntry(
                    role=role,
                    relative_path=relative,
                    sha256=sha256_file(path_abs),
                    size=os.path.getsize(path_abs),
                )
            )
        entries.sort(key=lambda entry: entry.relative_path)

        # El generador HTML heredado puede haber producido un reporte de hash
        # provisional con el mismo nombre. Se elimina dentro del staging; solo
        # este manifiesto cerrado puede llegar a publicarse.
        if os.path.exists(manifest_path):
            os.remove(manifest_path)
        _write_manifest(
            manifest_path,
            mode=mode,
            final_status=status,
            executed_at=executed_at or datetime.now(timezone.utc).isoformat(),
            input_metadata=input_metadata,
            entries=entries,
            unhashed_files=tuple(unhashed_files),
        )
        _validate_regular_file(manifest_path)

        # Hook de integridad para entradas que viven fuera de work_dir (XLSX):
        # se ejecuta tras cerrar el manifiesto y en la instrucción anterior al
        # rename, reduciendo la ventana entre rehash de entrada y publicación.
        if pre_publish_check is not None:
            pre_publish_check()

        transaction.publish()
        final_manifest = os.path.join(transaction.final_dir, os.path.basename(manifest_path))
        final_artifacts: Dict[str, str] = {}
        for role, staging_path in explicit_roles.items():
            relative = _relative_to_work(staging_path, transaction.work_dir)
            final_artifacts[role] = os.path.join(transaction.final_dir, *Path(relative).parts)

        # Solo lectura tras publicar: ningún artefacto se reescribe después
        # de registrar su digest.
        for entry in entries:
            final_path = os.path.join(transaction.final_dir, *Path(entry.relative_path).parts)
            if sha256_file(final_path) != entry.sha256:
                raise OutputValidationError(
                    f"La integridad cambió durante la publicación: {entry.relative_path}"
                )

        return PublicationResult(
            status=status,
            final_dir=transaction.final_dir,
            artifacts=final_artifacts,
            manifest_path=final_manifest,
            entries=tuple(entries),
            warnings=tuple(warnings),
        )
    except Exception:
        transaction.abort()
        raise
