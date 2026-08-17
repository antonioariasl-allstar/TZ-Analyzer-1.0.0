"""tools/build_windows.py: preflight, paths y construcción de comandos.

No ejecuta PyInstaller ni ninguna build real (ver P1-BUILD-CONFIG, sección
29): ``run_pyinstaller`` se verifica interceptando ``subprocess.run``.
"""
from __future__ import annotations

import sys

import pytest

import tools.build_windows as build_windows


def test_check_python_passes_on_current_interpreter():
    build_windows.check_python()  # no debe lanzar bajo 3.12+


def test_check_python_rejects_old_version(monkeypatch):
    monkeypatch.setattr(build_windows.sys, "version_info", (3, 11, 0))
    with pytest.raises(build_windows.BuildError):
        build_windows.check_python()


def test_check_pyinstaller_installed_raises_when_absent(monkeypatch):
    monkeypatch.setattr(build_windows.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(build_windows.BuildError):
        build_windows.check_pyinstaller_installed()


def test_check_pyinstaller_installed_passes_when_present(monkeypatch):
    monkeypatch.setattr(build_windows.importlib.util, "find_spec", lambda name: object())
    build_windows.check_pyinstaller_installed()  # no debe lanzar


def test_clean_packaging_artifacts_only_touches_packaging_dirs(tmp_path, monkeypatch):
    build_dir = tmp_path / "build" / "pyinstaller"
    dist_dir = tmp_path / "dist" / "TZ Analyzer"
    build_dir.mkdir(parents=True)
    dist_dir.mkdir(parents=True)
    (build_dir / "version_info.txt").write_text("x", encoding="utf-8")
    (dist_dir / "TZ Analyzer.exe").write_bytes(b"x")

    other_build_artifact = tmp_path / "build" / "manual" / "manual.html"
    other_build_artifact.parent.mkdir(parents=True)
    other_build_artifact.write_text("x", encoding="utf-8")

    monkeypatch.setattr(build_windows, "BUILD_PYINSTALLER_DIR", build_dir)
    monkeypatch.setattr(build_windows, "DIST_DIR", dist_dir)

    build_windows.clean_packaging_artifacts()

    assert not build_dir.exists()
    assert not dist_dir.exists()
    assert other_build_artifact.exists()  # build/manual no es responsabilidad de este helper


def test_clean_packaging_artifacts_tolerates_missing_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(build_windows, "BUILD_PYINSTALLER_DIR", tmp_path / "does-not-exist-1")
    monkeypatch.setattr(build_windows, "DIST_DIR", tmp_path / "does-not-exist-2")
    build_windows.clean_packaging_artifacts()  # no debe lanzar


def test_run_pyinstaller_invokes_expected_command(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check

    monkeypatch.setattr(build_windows.subprocess, "run", fake_run)
    build_windows.run_pyinstaller()

    assert captured["cmd"] == [sys.executable, "-m", "PyInstaller", "--clean", str(build_windows.SPEC_PATH)]
    assert captured["cwd"] == str(build_windows.REPO_ROOT)
    assert captured["check"] is True


def test_copy_manual_to_dist(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist" / "TZ Analyzer"
    dist_dir.mkdir(parents=True)
    monkeypatch.setattr(build_windows, "DIST_DIR", dist_dir)

    manual_source = tmp_path / "manual.html"
    manual_source.write_text("contenido", encoding="utf-8")

    destination = build_windows.copy_manual_to_dist(manual_source)

    assert destination == dist_dir / build_windows.MANUAL_FILENAME
    assert destination.read_text(encoding="utf-8") == "contenido"


def test_verify_dist_raises_when_exe_missing(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist" / "TZ Analyzer"
    dist_dir.mkdir(parents=True)
    (dist_dir / build_windows.MANUAL_FILENAME).write_text("x", encoding="utf-8")
    monkeypatch.setattr(build_windows, "DIST_DIR", dist_dir)

    with pytest.raises(build_windows.BuildError):
        build_windows.verify_dist()


def test_verify_dist_raises_when_manual_missing(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist" / "TZ Analyzer"
    dist_dir.mkdir(parents=True)
    (dist_dir / "TZ Analyzer.exe").write_bytes(b"x")
    monkeypatch.setattr(build_windows, "DIST_DIR", dist_dir)

    with pytest.raises(build_windows.BuildError):
        build_windows.verify_dist()


def test_verify_dist_passes_when_both_present(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist" / "TZ Analyzer"
    dist_dir.mkdir(parents=True)
    (dist_dir / "TZ Analyzer.exe").write_bytes(b"x")
    (dist_dir / build_windows.MANUAL_FILENAME).write_text("x", encoding="utf-8")
    monkeypatch.setattr(build_windows, "DIST_DIR", dist_dir)

    build_windows.verify_dist()  # no debe lanzar
