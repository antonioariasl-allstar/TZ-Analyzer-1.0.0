"""tools/build_version_info.py: semántica del version-info generado, no whitespace."""
from __future__ import annotations

from pathlib import Path

import tz_version
from tools.build_version_info import generate, render_version_info


def test_uses_windows_file_version_for_filevers_and_prodvers():
    text = render_version_info()
    expected = repr(tuple(tz_version.WINDOWS_FILE_VERSION))
    assert f"filevers={expected}" in text
    assert f"prodvers={expected}" in text


def test_product_version_string_matches_display_version():
    text = render_version_info()
    assert f"StringStruct(u'ProductVersion', u'{tz_version.VERSION}')" in text


def test_product_name_correct():
    text = render_version_info()
    assert f"StringStruct(u'ProductName', u'{tz_version.PRODUCT_NAME}')" in text
    assert f"StringStruct(u'InternalName', u'{tz_version.PRODUCT_NAME}')" in text


def test_original_filename_correct():
    text = render_version_info()
    assert f"StringStruct(u'OriginalFilename', u'{tz_version.EXECUTABLE_NAME}')" in text


def test_file_description_correct():
    text = render_version_info()
    assert f"StringStruct(u'FileDescription', u'{tz_version.FILE_DESCRIPTION}')" in text


def test_copyright_correct():
    text = render_version_info()
    assert f"StringStruct(u'LegalCopyright', u'{tz_version.COPYRIGHT}')" in text


def test_file_version_string_matches_tz_version():
    text = render_version_info()
    assert f"StringStruct(u'FileVersion', u'{tz_version.FILE_VERSION}')" in text


def test_empty_company_name_is_preserved():
    assert tz_version.COMPANY_NAME == ""
    text = render_version_info()
    assert "StringStruct(u'CompanyName', u'')" in text


def test_output_has_no_absolute_repo_path():
    text = render_version_info()
    repo_root = str(Path(__file__).resolve().parent.parent.parent)
    assert repo_root not in text
    assert "C:\\" not in text
    assert "C:/" not in text


def test_output_has_no_timestamp_markers():
    text = render_version_info()
    assert "date=(0, 0)" in text


def test_repeated_generation_is_byte_identical():
    assert render_version_info() == render_version_info()


def test_generate_writes_deterministic_file(tmp_path):
    out1 = generate(tmp_path / "one" / "version_info.txt")
    out2 = generate(tmp_path / "two" / "version_info.txt")
    assert out1.read_bytes() == out2.read_bytes()


def test_generate_creates_missing_output_directory(tmp_path):
    target = tmp_path / "nested" / "dir" / "version_info.txt"
    assert not target.parent.exists()
    result = generate(target)
    assert result == target
    assert target.is_file()


def test_translation_language_and_codepage_documented_combo():
    text = render_version_info()
    assert "u'040904B0'" in text
    assert "VarStruct(u'Translation', [1033, 1200])" in text
