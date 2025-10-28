#!/usr/bin/env python3
"""
Auditor de código desactivado/legacy
- Busca patrones comunes de código comentado o desactivado que podrían limpiarse
- Genera un reporte JSON con ubicaciones y contexto
"""
from __future__ import annotations
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    (r"MINA DESACTIVADA", "flag_desactivado"),
    (r"desactivad[oa]", "desactivado"),
    (r"deshabilitad[oa]", "deshabilitado"),
    (r"disabled", "disabled"),
    (r"deprecated|obsoleto", "deprecated"),
    (r"if\s+False\s*:\s*$", "if_false"),
    (r"return\s+.*#\s*TEMP|return\s+.*#\s*TODO", "return_temporal"),
    (r"#\s*TODO|#\s*HACK|#\s*FIXME", "todo_marker"),
]

EXCLUDE_DIRS = {'.venv', '.venv312', '__pycache__', '.pytest_cache', '.git'}


def scan_file(path: Path):
    findings = []
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return findings

    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        for patt, tag in PATTERNS:
            if re.search(patt, line, flags=re.IGNORECASE):
                # Capturar 2 líneas de contexto alrededor
                start = max(1, i-2)
                end = min(len(lines), i+2)
                snippet = "\n".join(lines[start-1:end])
                findings.append({
                    'line': i,
                    'tag': tag,
                    'pattern': patt,
                    'context': snippet,
                })
    return findings


def main():
    report = {}
    for path in ROOT.rglob('*.py'):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        f = scan_file(path)
        if f:
            report[str(path.relative_to(ROOT))] = f

    out = ROOT / 'tools' / 'reporte_codigo_muerto.json'
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

    total = sum(len(v) for v in report.values())
    print(f"🔎 Auditoría completada: {total} hallazgos en {len(report)} archivos")
    print(f"📄 Reporte: {out}")

    # Mostrar top 10 hallazgos breves en consola
    shown = 0
    for file, findings in report.items():
        for f in findings:
            print(f"- {file}:L{f['line']} [{f['tag']}] → {f['context'].splitlines()[2] if len(f['context'].splitlines())>=3 else ''}")
            shown += 1
            if shown >= 10:
                return


if __name__ == '__main__':
    main()
