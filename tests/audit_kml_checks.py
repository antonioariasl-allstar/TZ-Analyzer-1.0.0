import os
import sys
import zipfile
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from script_principal_bitacoras_refactory import generar_kml, bootstrap_config


def extract_kml(kmz_path):
    with zipfile.ZipFile(kmz_path, 'r') as z:
        for n in z.namelist():
            if n.lower().endswith('.kml'):
                return z.read(n).decode('utf-8', errors='ignore')
    return ''


def run_checks(out_dir):
    cases = []
    # Caso 1: direccion == antena -> debe ocultarse linea
    cases.append({
        'df': pd.DataFrame([{
            'fecha':'01/01/2025','hora':'10:00:00','lat':13.7,'long':-89.2,'azimut':120,
            'antena':'Calle 1, Col. Centro, San Salvador',
            'direccion':'Calle 1, Col. Centro, San Salvador',
            'tel':'70000000','imei':'350000000000000'
        }]),
        'expect_dir_line': False
    })
    # Caso 2: direccion distinta -> debe mostrarse
    cases.append({
        'df': pd.DataFrame([{
            'fecha':'01/01/2025','hora':'10:00:00','lat':13.7,'long':-89.2,'azimut':120,
            'antena':'Calle 1, Col. Centro, San Salvador',
            'direccion':'Otra direccion',
            'tel':'70000000','imei':'350000000000000'
        }]),
        'expect_dir_line': True
    })
    # Caso 3: compactación por segunda coma
    cases.append({
        'df': pd.DataFrame([{
            'fecha':'01/01/2025','hora':'10:00:00','lat':13.7,'long':-89.2,'azimut':120,
            'antena':'Aaaa Bbbb, Cccc Dddd, Eeee Ffff, Gggg',
            'direccion':'Dummy','tel':'70000000','imei':'350000000000000'
        }]),
        'expect_name_contains': 'Aaaa Bbbb, Cccc Dddd'
    })
    # Caso 4: compactación por palabras (5 sin artículos)
    cases.append({
        'df': pd.DataFrame([{
            'fecha':'01/01/2025','hora':'10:00:00','lat':13.7,'long':-89.2,'azimut':120,
            'antena':'El Gran Sitio De Las Flores Hermosas',
            'direccion':'Dummy','tel':'70000000','imei':'350000000000000'
        }]),
        'expect_name_words': 5
    })

    bootstrap_config()

    import re
    results = []
    for i, case in enumerate(cases, start=1):
        out_kml = os.path.join(out_dir, f'audit_{i}.kml')
        generar_kml(case['df'], out_kml, flat=True)
        kmz = os.path.splitext(out_kml)[0] + '.kmz'
        kml_text = extract_kml(kmz)

        ok = True
        notes = []
        kml_frag = ''
        # Extraer primer <Placemark> para mostrar fragmento relevante
        placemark = re.search(r'<Placemark>(.*?)</Placemark>', kml_text, re.DOTALL)
        if placemark:
            kml_frag = placemark.group(1)
        # Validar Dirección
        if 'expect_dir_line' in case:
            has_dir = ('<b>Direccion:</b>' in kml_text)
            if has_dir != case['expect_dir_line']:
                ok = False
                notes.append(f"Direccion present={has_dir} expected={case['expect_dir_line']}")
                if kml_frag:
                    notes.append(f"KML fragment:\n{kml_frag.strip()[:300]}")
        # Validar compactación exacta del <name>
        if 'expect_name_contains' in case:
            m = re.search(r'<name>(.*?)</name>', kml_text)
            actual_name = m.group(1).strip() if m else ''
            expected = case['expect_name_contains']
            if actual_name != expected:
                ok = False
                notes.append(f"<name> mismatch: actual='{actual_name}' expected='{expected}'")
                if kml_frag:
                    notes.append(f"KML fragment:\n{kml_frag.strip()[:300]}")
        # Validar número de palabras en <name>
        if 'expect_name_words' in case:
            m = re.search(r'<name>(.*?)</name>', kml_text)
            actual_name = m.group(1).strip() if m else ''
            words = [w for w in re.split(r'\s+', actual_name) if w]
            if len(words) < case['expect_name_words']:
                ok = False
                notes.append(f"name words {len(words)} < expected {case['expect_name_words']} (actual='{actual_name}')")
                if kml_frag:
                    notes.append(f"KML fragment:\n{kml_frag.strip()[:300]}")

        results.append((i, ok, '; '.join(notes)))

    return results


if __name__ == '__main__':
    out_dir = os.path.join(ROOT, 'tests', 'out')
    os.makedirs(out_dir, exist_ok=True)
    res = run_checks(out_dir)
    for i, ok, notes in res:
        print(f"Case {i}: {'PASS' if ok else 'FAIL'} {notes}")
