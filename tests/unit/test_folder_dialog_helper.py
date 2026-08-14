"""Pruebas del selector Tk aislado y de su protocolo JSON interno."""

from __future__ import annotations

import json
import os
import stat
import sys
import types
from pathlib import Path
from typing import Any

import pytest

import tz_folder_dialog_helper as helper
import tz_folder_dialog_ipc as ipc


_REQUEST_ID = "a" * 64


class _FakeTclError(RuntimeError):
    pass


class _FakeRoot:
    def __init__(self) -> None:
        self.withdrawn = False
        self.destroyed = False
        self.attrs: dict[str, Any] = {}

    def withdraw(self) -> None:
        self.withdrawn = True

    def attributes(self, name: str, value: Any) -> None:
        self.attrs[name] = value

    def destroy(self) -> None:
        self.destroyed = True


def _install_fake_tkinter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    askdirectory_result: str = "",
    askdirectory_raises: BaseException | None = None,
    tk_raises: BaseException | None = None,
) -> tuple[_FakeRoot, Any]:
    fake_root = _FakeRoot()

    def fake_tk() -> _FakeRoot:
        if tk_raises is not None:
            raise tk_raises
        return fake_root

    def fake_askdirectory(**kwargs: Any) -> str:
        fake_askdirectory.kwargs = kwargs
        if askdirectory_raises is not None:
            raise askdirectory_raises
        return askdirectory_result

    fake_askdirectory.kwargs = {}
    fake_filedialog = types.ModuleType("tkinter.filedialog")
    fake_filedialog.askdirectory = fake_askdirectory
    fake_tkinter = types.ModuleType("tkinter")
    fake_tkinter.Tk = fake_tk
    fake_tkinter.TclError = _FakeTclError
    fake_tkinter.filedialog = fake_filedialog

    monkeypatch.setitem(sys.modules, "tkinter", fake_tkinter)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", fake_filedialog)
    return fake_root, fake_askdirectory


def test_select_folder_success_preserves_tk_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = "C:\\Casos con espacios\\Peña y análisis 𐍈"
    root, askdirectory = _install_fake_tkinter(
        monkeypatch,
        askdirectory_result=selected,
    )

    outcome = helper.select_folder(
        title="Elegir carpeta del caso",
        initial_dir="C:\\Casos iniciales",
    )

    assert outcome == helper.DialogOutcome(ipc.STATUS_SUCCESS, path=selected)
    assert root.withdrawn is True
    assert root.attrs == {"-topmost": True}
    assert askdirectory.kwargs == {
        "title": "Elegir carpeta del caso",
        "initialdir": "C:\\Casos iniciales",
        "mustexist": True,
    }
    assert root.destroyed is True


def test_select_folder_cancel_uses_defaults_and_destroys_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, askdirectory = _install_fake_tkinter(monkeypatch, askdirectory_result="")

    outcome = helper.select_folder()

    assert outcome == helper.DialogOutcome(ipc.STATUS_CANCELLED)
    assert askdirectory.kwargs == {
        "title": helper._DEFAULT_TITLE,
        "initialdir": None,
        "mustexist": True,
    }
    assert root.destroyed is True


def test_select_folder_reports_unavailable_when_tkinter_cannot_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "tkinter", None)

    outcome = helper.select_folder()

    assert outcome == helper.DialogOutcome(
        ipc.STATUS_UNAVAILABLE,
        error_code="TKINTER_UNAVAILABLE",
    )


def test_select_folder_reports_unavailable_and_destroys_root_on_tcl_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _askdirectory = _install_fake_tkinter(
        monkeypatch,
        askdirectory_raises=_FakeTclError("no display"),
    )

    outcome = helper.select_folder()

    assert outcome == helper.DialogOutcome(
        ipc.STATUS_UNAVAILABLE,
        error_code="TK_UNAVAILABLE",
    )
    assert root.destroyed is True


def test_select_folder_reports_error_and_destroys_root_on_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _askdirectory = _install_fake_tkinter(
        monkeypatch,
        askdirectory_raises=ValueError("sensitive path must not escape"),
    )

    outcome = helper.select_folder()

    assert outcome == helper.DialogOutcome(
        ipc.STATUS_ERROR,
        error_code="UNEXPECTED_DIALOG_ERROR",
    )
    assert root.destroyed is True


def test_select_folder_reports_unavailable_when_tk_cannot_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_tkinter(
        monkeypatch,
        tk_raises=_FakeTclError("desktop unavailable"),
    )

    outcome = helper.select_folder()

    assert outcome == helper.DialogOutcome(
        ipc.STATUS_UNAVAILABLE,
        error_code="TK_UNAVAILABLE",
    )


def test_internal_json_roundtrip_is_utf8_and_keeps_unicode_and_spaces(
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dialog_dir = tmp_path / "dialog"
    title = "Elegir carpeta para Peña: análisis, síntesis y canción 𐍈"
    initial_dir = "C:\\Casos con espacios\\Niñez y música 𐍈"
    selected = "C:\\Salida final\\Muñoz, síntesis y álbum 𐍈"
    request_file = ipc.write_request(
        _REQUEST_ID,
        title=title,
        initial_dir=initial_dir,
        dialog_dir=dialog_dir,
    )
    received: dict[str, Any] = {}

    def fake_select_folder(**kwargs: Any) -> helper.DialogOutcome:
        received.update(kwargs)
        return helper.DialogOutcome(ipc.STATUS_SUCCESS, path=selected)

    exit_code = helper.run_internal_folder_dialog(
        _REQUEST_ID,
        dialog_dir=dialog_dir,
        select_folder_fn=fake_select_folder,
    )

    assert exit_code == ipc.EXIT_OK
    assert received == {"title": title, "initial_dir": initial_dir}
    assert ipc.read_result(_REQUEST_ID, dialog_dir=dialog_dir) == {
        "schema": ipc.PROTOCOL_SCHEMA,
        "request_id": _REQUEST_ID,
        "status": ipc.STATUS_SUCCESS,
        "path": selected,
        "error_code": None,
    }
    result_file = ipc.result_path(_REQUEST_ID, dialog_dir=dialog_dir)
    for raw_json in (request_file.read_bytes(), result_file.read_bytes()):
        raw_json.decode("utf-8", errors="strict")
        assert "ñ".encode("utf-8") in raw_json
        assert "í".encode("utf-8") in raw_json
        assert " ".encode("utf-8") in raw_json
        assert "𐍈".encode("utf-8") in raw_json
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert selected not in captured.out
    assert selected not in captured.err


@pytest.mark.parametrize(
    ("request_id", "outcome", "expected_exit"),
    [
        pytest.param(
            "0" * 64,
            helper.DialogOutcome(ipc.STATUS_SUCCESS, path="C:\\Salida segura"),
            ipc.EXIT_OK,
            id="success-0",
        ),
        pytest.param(
            "1" * 64,
            helper.DialogOutcome(ipc.STATUS_CANCELLED),
            ipc.EXIT_CANCELLED,
            id="cancelled-3",
        ),
        pytest.param(
            "2" * 64,
            helper.DialogOutcome(ipc.STATUS_UNAVAILABLE, error_code="TK_UNAVAILABLE"),
            ipc.EXIT_NO_GUI,
            id="unavailable-4",
        ),
        pytest.param(
            "3" * 64,
            helper.DialogOutcome(ipc.STATUS_ERROR, error_code="UNEXPECTED_DIALOG_ERROR"),
            ipc.EXIT_ERROR,
            id="error-1",
        ),
    ],
)
def test_internal_statuses_write_structured_result_and_map_exit_codes(
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
    request_id: str,
    outcome: helper.DialogOutcome,
    expected_exit: int,
) -> None:
    dialog_dir = tmp_path / "dialog"
    ipc.write_request(
        request_id,
        title="Seleccionar salida",
        initial_dir="C:\\Inicio",
        dialog_dir=dialog_dir,
    )

    exit_code = helper.run_internal_folder_dialog(
        request_id,
        dialog_dir=dialog_dir,
        select_folder_fn=lambda **_kwargs: outcome,
    )

    assert exit_code == expected_exit
    assert ipc.read_result(request_id, dialog_dir=dialog_dir) == {
        "schema": ipc.PROTOCOL_SCHEMA,
        "request_id": request_id,
        "status": outcome.status,
        "path": outcome.path,
        "error_code": outcome.error_code,
    }
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize(
    "malformed_payload",
    [
        pytest.param("{not valid JSON", id="invalid-json"),
        pytest.param(
            json.dumps(
                {
                    "schema": ipc.PROTOCOL_SCHEMA,
                    "request_id": _REQUEST_ID,
                    "title": "Falta initial_dir",
                }
            ),
            id="invalid-shape",
        ),
    ],
)
def test_internal_mode_rejects_malformed_request_and_publishes_safe_error(
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
    malformed_payload: str,
) -> None:
    dialog_dir = tmp_path / "dialog"
    request_file = ipc.request_path(_REQUEST_ID, dialog_dir=dialog_dir)
    request_file.parent.mkdir(parents=True)
    request_file.write_text(malformed_payload, encoding="utf-8")
    selector_called = False

    def selector_must_not_run(**_kwargs: Any) -> helper.DialogOutcome:
        nonlocal selector_called
        selector_called = True
        return helper.DialogOutcome(ipc.STATUS_SUCCESS, path="C:\\No debe usarse")

    exit_code = helper.run_internal_folder_dialog(
        _REQUEST_ID,
        dialog_dir=dialog_dir,
        select_folder_fn=selector_must_not_run,
    )

    assert exit_code == ipc.EXIT_ERROR
    assert selector_called is False
    assert ipc.read_result(_REQUEST_ID, dialog_dir=dialog_dir) == {
        "schema": ipc.PROTOCOL_SCHEMA,
        "request_id": _REQUEST_ID,
        "status": ipc.STATUS_ERROR,
        "path": None,
        "error_code": "INVALID_REQUEST",
    }
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_internal_mode_converts_selector_exception_to_sanitized_error(
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dialog_dir = tmp_path / "dialog"
    sensitive_path = "C:\\Caso reservado\\persona"
    ipc.write_request(
        _REQUEST_ID,
        title="Seleccionar",
        initial_dir=sensitive_path,
        dialog_dir=dialog_dir,
    )

    def broken_selector(**_kwargs: Any) -> helper.DialogOutcome:
        raise RuntimeError(f"fallo en {sensitive_path}")

    exit_code = helper.run_internal_folder_dialog(
        _REQUEST_ID,
        dialog_dir=dialog_dir,
        select_folder_fn=broken_selector,
    )

    assert exit_code == ipc.EXIT_ERROR
    assert ipc.read_result(_REQUEST_ID, dialog_dir=dialog_dir)["error_code"] == (
        "UNEXPECTED_DIALOG_ERROR"
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert sensitive_path not in captured.out
    assert sensitive_path not in captured.err


@pytest.mark.parametrize(
    "invalid_request_id",
    [
        pytest.param("../escape", id="forward-traversal"),
        pytest.param("..\\escape", id="backslash-traversal"),
        pytest.param("a" * 63, id="too-short"),
        pytest.param("A" * 64, id="uppercase"),
        pytest.param("g" * 64, id="non-hex"),
        pytest.param(None, id="not-a-string"),
    ],
)
def test_ipc_rejects_invalid_or_traversal_request_ids_before_path_construction(
    tmp_path: Any,
    invalid_request_id: object,
) -> None:
    dialog_dir = tmp_path / "dialog"

    with pytest.raises(ipc.DialogProtocolError):
        ipc.request_path(invalid_request_id, dialog_dir=dialog_dir)
    with pytest.raises(ipc.DialogProtocolError):
        ipc.result_path(invalid_request_id, dialog_dir=dialog_dir)

    assert dialog_dir.exists() is False


def test_internal_mode_rejects_traversal_id_without_io_or_selector(
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dialog_dir = tmp_path / "dialog"
    selector_called = False

    def selector_must_not_run(**_kwargs: Any) -> helper.DialogOutcome:
        nonlocal selector_called
        selector_called = True
        return helper.DialogOutcome(ipc.STATUS_CANCELLED)

    exit_code = helper.run_internal_folder_dialog(
        "..\\..\\outside",
        dialog_dir=dialog_dir,
        select_folder_fn=selector_must_not_run,
    )

    assert exit_code == ipc.EXIT_ERROR
    assert selector_called is False
    assert dialog_dir.exists() is False
    assert list(tmp_path.iterdir()) == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


_TTL_NOW = 2_000_000_000.0


def _make_stale(path: Any) -> None:
    stale_mtime = _TTL_NOW - ipc.DIALOG_IPC_TTL_SECONDS - 1
    os.utime(path, (stale_mtime, stale_mtime))


def test_cleanup_ttl_removes_stale_request_and_result(tmp_path: Any) -> None:
    dialog_dir = tmp_path / "dialog"
    request_file = ipc.write_request(
        _REQUEST_ID,
        title="Solicitud abandonada",
        initial_dir="C:\\Caso reservado",
        dialog_dir=dialog_dir,
    )
    result_file = ipc.write_result(
        _REQUEST_ID,
        status=ipc.STATUS_CANCELLED,
        dialog_dir=dialog_dir,
    )
    _make_stale(request_file)
    _make_stale(result_file)

    removed = ipc.cleanup_stale_dialog_ipc(
        dialog_dir=dialog_dir,
        now=_TTL_NOW,
    )

    assert removed == 2
    assert request_file.exists() is False
    assert result_file.exists() is False


def test_cleanup_ttl_preserves_recent_request_and_result(tmp_path: Any) -> None:
    dialog_dir = tmp_path / "dialog"
    request_file = ipc.write_request(
        _REQUEST_ID,
        title="Solicitud reciente",
        initial_dir=None,
        dialog_dir=dialog_dir,
    )
    result_file = ipc.write_result(
        _REQUEST_ID,
        status=ipc.STATUS_CANCELLED,
        dialog_dir=dialog_dir,
    )
    recent_mtime = _TTL_NOW - ipc.DIALOG_IPC_TTL_SECONDS + 1
    for path in (request_file, result_file):
        os.utime(path, (recent_mtime, recent_mtime))

    removed = ipc.cleanup_stale_dialog_ipc(
        dialog_dir=dialog_dir,
        now=_TTL_NOW,
    )

    assert removed == 0
    assert request_file.exists() is True
    assert result_file.exists() is True


def test_cleanup_ttl_preserves_stale_files_with_foreign_names(tmp_path: Any) -> None:
    dialog_dir = tmp_path / "dialog"
    dialog_dir.mkdir()
    foreign_files = [
        dialog_dir / "notes.json",
        dialog_dir / "dialog-request-not-hex.json",
        dialog_dir / f"dialog-request-{'b' * 64}.json.bak",
        dialog_dir / f".dialog-result-{'c' * 64}-short.tmp",
        dialog_dir / f".dialog-request-{'d' * 64}-abcdefgh.tmp.bak",
    ]
    for path in foreign_files:
        path.write_text("no pertenece al IPC", encoding="utf-8")
        _make_stale(path)

    removed = ipc.cleanup_stale_dialog_ipc(
        dialog_dir=dialog_dir,
        now=_TTL_NOW,
    )

    assert removed == 0
    assert all(path.exists() for path in foreign_files)


def test_cleanup_ttl_preserves_exact_name_without_matching_schema_or_id(
    tmp_path: Any,
) -> None:
    dialog_dir = tmp_path / "dialog"
    dialog_dir.mkdir()
    wrong_schema = dialog_dir / f"dialog-request-{'8' * 64}.json"
    wrong_id = dialog_dir / f"dialog-result-{'9' * 64}.json"
    wrong_schema.write_text(
        json.dumps({"schema": "FOREIGN", "request_id": "8" * 64}),
        encoding="utf-8",
    )
    wrong_id.write_text(
        json.dumps({"schema": ipc.PROTOCOL_SCHEMA, "request_id": "0" * 64}),
        encoding="utf-8",
    )
    for path in (wrong_schema, wrong_id):
        _make_stale(path)

    assert ipc.cleanup_stale_dialog_ipc(dialog_dir=dialog_dir, now=_TTL_NOW) == 0
    assert wrong_schema.exists() is True
    assert wrong_id.exists() is True


def test_cleanup_ttl_removes_stale_owned_publication_temporaries(tmp_path: Any) -> None:
    dialog_dir = tmp_path / "dialog"
    dialog_dir.mkdir()
    temporary_files = [
        dialog_dir / f".dialog-request-{'e' * 64}-abc123_4.tmp",
        dialog_dir / f".dialog-result-{'f' * 64}-8765_wxy.tmp",
    ]
    for path in temporary_files:
        path.write_text("publicacion interrumpida", encoding="utf-8")
        _make_stale(path)

    removed = ipc.cleanup_stale_dialog_ipc(
        dialog_dir=dialog_dir,
        now=_TTL_NOW,
    )

    assert removed == 2
    assert all(path.exists() is False for path in temporary_files)


def test_cleanup_ttl_does_not_follow_symlink_when_supported(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog_dir = tmp_path / "dialog"
    dialog_dir.mkdir()
    outside_file = tmp_path / "outside-sensitive.txt"
    outside_file.write_text("debe conservarse", encoding="utf-8")
    link_file = dialog_dir / f"dialog-result-{'1' * 64}.json"
    try:
        os.symlink(outside_file, link_file)
    except (NotImplementedError, OSError):
        metadata = types.SimpleNamespace(
            st_mode=stat.S_IFLNK,
            st_mtime=_TTL_NOW - ipc.DIALOG_IPC_TTL_SECONDS - 1,
            st_file_attributes=0,
        )

        class FakeLinkEntry:
            name = link_file.name
            path = str(link_file)

            @staticmethod
            def stat(*, follow_symlinks: bool) -> Any:
                assert follow_symlinks is False
                return metadata

        class FakeScandir:
            def __enter__(self) -> Any:
                return iter([FakeLinkEntry()])

            def __exit__(self, *_args: Any) -> None:
                return None

        unlink_calls: list[str] = []
        monkeypatch.setattr(ipc.os, "scandir", lambda _path: FakeScandir())
        monkeypatch.setattr(ipc.os, "unlink", lambda path: unlink_calls.append(path))
        assert ipc.cleanup_stale_dialog_ipc(dialog_dir=dialog_dir, now=_TTL_NOW) == 0
        assert unlink_calls == []
        assert outside_file.read_text(encoding="utf-8") == "debe conservarse"
        return

    link_metadata = link_file.lstat()
    now = link_metadata.st_mtime + ipc.DIALOG_IPC_TTL_SECONDS + 1

    removed = ipc.cleanup_stale_dialog_ipc(dialog_dir=dialog_dir, now=now)

    assert removed == 0
    assert link_file.is_symlink() is True
    assert outside_file.read_text(encoding="utf-8") == "debe conservarse"


def test_cleanup_ttl_does_not_follow_dialog_base_symlink_or_reparse(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside_dialog = tmp_path / "outside-dialog"
    stale_file = ipc.write_request(
        "5" * 64,
        title="No borrar fuera del directorio literal",
        initial_dir=None,
        dialog_dir=outside_dialog,
    )
    _make_stale(stale_file)
    linked_dialog = tmp_path / "dialog-link"

    try:
        os.symlink(outside_dialog, linked_dialog, target_is_directory=True)
    except (NotImplementedError, OSError):
        linked_dialog.mkdir()
        stale_file = ipc.write_request(
            "5" * 64,
            title="No borrar dentro de un reparse point",
            initial_dir=None,
            dialog_dir=linked_dialog,
        )
        _make_stale(stale_file)
        real_stat = os.stat
        base_metadata = real_stat(linked_dialog, follow_symlinks=False)
        reparse_metadata = types.SimpleNamespace(
            st_mode=base_metadata.st_mode,
            st_mtime=base_metadata.st_mtime,
            st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
        )
        scandir_calls: list[Any] = []

        def fake_stat(path: Any, *args: Any, **kwargs: Any) -> Any:
            if Path(os.path.abspath(os.fspath(path))) == linked_dialog.absolute():
                assert kwargs.get("follow_symlinks") is False
                return reparse_metadata
            return real_stat(path, *args, **kwargs)

        with monkeypatch.context() as scoped:
            scoped.setattr(ipc.os, "stat", fake_stat)
            scoped.setattr(
                ipc.os,
                "scandir",
                lambda path: scandir_calls.append(path),
            )
            removed = ipc.cleanup_stale_dialog_ipc(
                dialog_dir=linked_dialog,
                now=_TTL_NOW,
            )

        assert removed == 0
        assert scandir_calls == []
        assert stale_file.exists() is True
        return

    removed = ipc.cleanup_stale_dialog_ipc(
        dialog_dir=linked_dialog,
        now=_TTL_NOW,
    )

    assert removed == 0
    assert linked_dialog.is_symlink() is True
    assert stale_file.exists() is True


def test_cleanup_ttl_rejects_reparse_component_below_localappdata_anchor(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    localappdata = tmp_path / "LocalAppData"
    product_dir = localappdata / "TZ Analyzer"
    dialog_dir = product_dir / "run" / "dialog"
    stale_file = ipc.write_request(
        "6" * 64,
        title="No atravesar un componente reparse",
        initial_dir=None,
        dialog_dir=dialog_dir,
    )
    _make_stale(stale_file)
    real_stat = os.stat
    product_metadata = real_stat(product_dir, follow_symlinks=False)
    reparse_metadata = types.SimpleNamespace(
        st_mode=product_metadata.st_mode,
        st_mtime=product_metadata.st_mtime,
        st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
    )
    inspected: list[Path] = []
    scandir_calls: list[Any] = []

    def fake_stat(path: Any, *args: Any, **kwargs: Any) -> Any:
        literal = Path(os.path.abspath(os.fspath(path)))
        inspected.append(literal)
        if literal == product_dir.absolute():
            assert kwargs.get("follow_symlinks") is False
            return reparse_metadata
        return real_stat(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setenv("LOCALAPPDATA", str(localappdata))
        scoped.setattr(ipc.os, "stat", fake_stat)
        scoped.setattr(
            ipc.os,
            "scandir",
            lambda path: scandir_calls.append(path),
        )
        removed = ipc.cleanup_stale_dialog_ipc(now=_TTL_NOW)

    assert removed == 0
    assert product_dir.absolute() in inspected
    assert dialog_dir.absolute() not in inspected
    assert scandir_calls == []
    assert stale_file.exists() is True


def test_cleanup_ttl_rejects_localappdata_anchor_reparse(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    localappdata = tmp_path / "LocalAppData"
    dialog_dir = localappdata / "TZ Analyzer" / "run" / "dialog"
    stale_file = ipc.write_request(
        "7" * 64,
        title="No atravesar el ancla reparse",
        initial_dir=None,
        dialog_dir=dialog_dir,
    )
    _make_stale(stale_file)
    real_stat = os.stat
    anchor_metadata = real_stat(localappdata, follow_symlinks=False)
    reparse_metadata = types.SimpleNamespace(
        st_mode=anchor_metadata.st_mode,
        st_mtime=anchor_metadata.st_mtime,
        st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
    )
    scandir_calls: list[Any] = []

    def fake_stat(path: Any, *args: Any, **kwargs: Any) -> Any:
        if Path(os.path.abspath(os.fspath(path))) == localappdata.absolute():
            assert kwargs.get("follow_symlinks") is False
            return reparse_metadata
        return real_stat(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setenv("LOCALAPPDATA", str(localappdata))
        scoped.setattr(ipc.os, "stat", fake_stat)
        scoped.setattr(
            ipc.os,
            "scandir",
            lambda path: scandir_calls.append(path),
        )
        removed = ipc.cleanup_stale_dialog_ipc(now=_TTL_NOW)

    assert removed == 0
    assert scandir_calls == []
    assert stale_file.exists() is True


def test_cleanup_ttl_rejects_reparse_entry_without_unlink(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_path = tmp_path / f"dialog-request-{'2' * 64}.json"
    metadata = types.SimpleNamespace(
        st_mode=stat.S_IFREG,
        st_mtime=_TTL_NOW - ipc.DIALOG_IPC_TTL_SECONDS - 1,
        st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
    )

    class FakeEntry:
        name = entry_path.name
        path = str(entry_path)

        @staticmethod
        def stat(*, follow_symlinks: bool) -> Any:
            assert follow_symlinks is False
            return metadata

    class FakeScandir:
        def __enter__(self) -> Any:
            return iter([FakeEntry()])

        def __exit__(self, *_args: Any) -> None:
            return None

    unlink_calls: list[str] = []
    monkeypatch.setattr(ipc.os, "scandir", lambda _path: FakeScandir())
    monkeypatch.setattr(ipc.os, "unlink", lambda path: unlink_calls.append(path))

    removed = ipc.cleanup_stale_dialog_ipc(
        dialog_dir=tmp_path,
        now=_TTL_NOW,
    )

    assert removed == 0
    assert unlink_calls == []


def test_cleanup_ttl_unlink_failure_is_best_effort_and_continues(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog_dir = tmp_path / "dialog"
    request_file = ipc.write_request(
        "3" * 64,
        title=None,
        initial_dir=None,
        dialog_dir=dialog_dir,
    )
    result_file = ipc.write_result(
        "4" * 64,
        status=ipc.STATUS_CANCELLED,
        dialog_dir=dialog_dir,
    )
    for path in (request_file, result_file):
        _make_stale(path)

    real_unlink = os.unlink
    unlink_calls: list[str] = []

    def fail_first_unlink(path: str) -> None:
        unlink_calls.append(os.fspath(path))
        if len(unlink_calls) == 1:
            raise PermissionError("archivo temporalmente ocupado")
        real_unlink(path)

    monkeypatch.setattr(ipc.os, "unlink", fail_first_unlink)

    removed = ipc.cleanup_stale_dialog_ipc(
        dialog_dir=dialog_dir,
        now=_TTL_NOW,
    )

    assert len(unlink_calls) == 2
    assert removed == 1
    assert sum(path.exists() for path in (request_file, result_file)) == 1
