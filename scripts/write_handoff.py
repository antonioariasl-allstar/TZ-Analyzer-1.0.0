"""Generador simple de CHAT_HANDOFF.md y CHAT_HANDOFF.json

Ejecutar desde la raíz del repo con el Python del venv:
    .\.env312\Scripts\python.exe scripts\write_handoff.py
"""
import json
import os
import subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_MD = os.path.join(ROOT, 'docs', 'CHAT_HANDOFF.md')
OUT_JSON = os.path.join(ROOT, 'docs', 'CHAT_HANDOFF.json')

def run_audit():
    cmd = [os.path.join('.', '.env312', 'Scripts', 'python.exe'), 'tests/audit_kml_checks.py']
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return p.returncode, p.stdout + p.stderr
    except Exception as e:
        return 1, str(e)

def main():
    rc, out = run_audit()
    summary = 'OK' if rc == 0 and 'PASS' in out else 'FAIL'
    data = {
        'date': datetime.utcnow().isoformat() + 'Z',
        'summary': summary,
        'audit_output': out,
        'files_changed': [
            'script_principal_bitacoras_refactory.py',
            'tests/audit_kml_checks.py'
        ],
        'notes': [
            'Compactación: 4 palabras si >40 chars, truncado a 40 si excede.'
        ]
    }
    # Write JSON
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Append/update MD
    md = f"""# CHAT HANDOFF

Fecha: {data['date']}

Resumen: {data['summary']}

Archivos cambiados:
\n"""
    for fn in data['files_changed']:
        md += f"- {fn}\n"
    # Añadir salida del audit en bloque de código
    md += "\nAudit output:\n\n"
    md += "```\n"
    md += data['audit_output'] or '(no output)'
    md += "\n```\n"
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write(md)

    print('Handoff written to', OUT_MD, 'and', OUT_JSON)

if __name__ == '__main__':
    main()
