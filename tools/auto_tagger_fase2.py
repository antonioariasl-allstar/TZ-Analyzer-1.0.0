#!/usr/bin/env python3
"""
AUTO-TAGGER FASE 2: Etiquetado sistemático masivo
Automatiza el etiquetado de las restantes 150+ funciones

Uso: python auto_tagger_fase2.py
"""

import re
import csv
from pathlib import Path

# Archivo principal
SCRIPT_FILE = Path("../script_principal_bitacoras_refactory.py")
CSV_FILE = Path("../docs/S0_TAGGING_INVENTORY.csv")
OUTPUT_LOG = Path("../docs/FASE2_AUTO_TAGGING_LOG.md")

# Funciones ya etiquetadas (Fase 1 + Lotes 1-3)
TAGGED_FUNCTIONS = {
    # Fase 1
    'generar_kml', 'generar_informe_html', 'hash_outputs', 'dedupe_columns', 'main',
    # Lote 1 - Validation
    '_wizard_qc_mapeo', 'validar_columnas', 'validar_datos',
    # Lote 2 - KML
    '_hex_to_kml_color', '_crear_feature_kml', 'compactar_nombre_antena_kml', '_fmt_coord',
    # Lote 3 - I/O
    'seleccionar_archivo', 'seleccionar_carpeta', '_file_hashes'
}

# Mapeo de patrones a paquetes y roles
PATTERN_MAPPING = {
    # KML Generation
    'kml|kmz|coord|placemark|polygon|geometry': {
        'pkg': 'tz_kml',
        'roles': {
            'color': 'style_generator',
            'crear|feature': 'feature_builder', 
            'coord': 'coordinate_converter',
            'default': 'kml_generator'
        }
    },
    
    # HTML Reports
    'html|report|informe|tabla|estilo|css': {
        'pkg': 'tz_services',
        'roles': {
            'html': 'html_generator',
            'heatmap': 'visualization_builder',
            'logo': 'asset_manager',
            'default': 'report_generator'
        }
    },
    
    # I/O Operations
    'leer|escribir|archivo|file|csv|tsv|save|load|seleccionar': {
        'pkg': 'tz_io',
        'roles': {
            'seleccionar': 'file_selector',
            'hash': 'integrity_checker',
            'sanear|nombre': 'name_sanitizer',
            'leer|load|read': 'file_reader',
            'escribir|save|write': 'file_writer',
            'default': 'io_handler'
        }
    },
    
    # Data Processing
    'proces|transform|parse|convert|filter|group': {
        'pkg': 'tz_core',
        'roles': {
            'group': 'data_grouper',
            'parse': 'data_parser',
            'transform': 'data_transformer',
            'default': 'data_processor'
        }
    },
    
    # Validation & QC
    'valid|check|verify|test|qc|audit': {
        'pkg': 'tz_services',
        'roles': {
            'qc_': 'quality_controller',
            'valid': 'data_validator',
            'audit': 'integrity_auditor',
            'default': 'validator'
        }
    },
    
    # Time Analysis
    'time|hora|timestamp|duracion|interval': {
        'pkg': 'tz_core',
        'roles': {
            'fmt': 'time_formatter',
            'duracion|interval': 'duration_calculator',
            'default': 'time_processor'
        }
    },
    
    # CLI Interface
    'cli|args|input|wizard|menu|prompt': {
        'pkg': 'tz_cli',
        'roles': {
            'wizard': 'wizard_controller',
            'menu': 'menu_handler',
            'input': 'input_validator',
            'default': 'cli_handler'
        }
    },
    
    # Utility Functions
    'util|helper|format|clean|normalize': {
        'pkg': 'tz_core',
        'roles': {
            'format|fmt': 'formatter',
            'clean|normalize': 'data_cleaner',
            'default': 'utility'
        }
    }
}

def find_all_functions(content):
    """Encuentra todas las funciones en el archivo"""
    func_pattern = r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    functions = []
    
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        match = re.match(func_pattern, line)
        if match:
            func_name = match.group(1)
            if func_name not in TAGGED_FUNCTIONS:
                functions.append((func_name, i))
    
    return functions

def categorize_function(func_name):
    """Categoriza una función según patrones"""
    func_lower = func_name.lower()
    
    for pattern_key, mapping in PATTERN_MAPPING.items():
        patterns = pattern_key.split('|')
        if any(re.search(pattern, func_lower) for pattern in patterns):
            pkg = mapping['pkg']
            
            # Determinar rol específico
            role = mapping['roles']['default']
            for role_pattern, role_name in mapping['roles'].items():
                if role_pattern != 'default' and re.search(role_pattern, func_lower):
                    role = role_name
                    break
            
            return pkg, role
    
    # Fallback para funciones no categorizadas
    return 'tz_legacy', 'legacy_function'

def estimate_function_size(content, func_name, start_line):
    """Estima el tamaño de una función"""
    lines = content.split('\n')
    
    # Buscar siguiente función o final de archivo
    end_line = len(lines)
    indent_level = None
    
    for i in range(start_line, len(lines)):
        line = lines[i]
        
        # Primer línea no vacía después de def para obtener indentación
        if indent_level is None and line.strip():
            if not line.strip().startswith('def '):
                indent_level = len(line) - len(line.lstrip())
        
        # Si encontramos otra función al mismo nivel, terminar
        if (i > start_line and 
            re.match(r'^\s*def\s+', line) and 
            indent_level is not None and
            (len(line) - len(line.lstrip())) <= indent_level):
            end_line = i
            break
    
    return end_line

def main():
    """Función principal"""
    print("🚀 AUTO-TAGGER FASE 2: Iniciando etiquetado masivo...")
    
    # Leer archivo principal
    with open(SCRIPT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Encontrar funciones pendientes
    pending_functions = find_all_functions(content)
    
    print(f"📊 Funciones pendientes: {len(pending_functions)}")
    print(f"✅ Funciones ya etiquetadas: {len(TAGGED_FUNCTIONS)}")
    
    # Procesar funciones en lotes
    log_entries = []
    batch_size = 25
    total_batches = (len(pending_functions) + batch_size - 1) // batch_size
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(pending_functions))
        batch_functions = pending_functions[start_idx:end_idx]
        
        print(f"\n📦 LOTE {batch_num + 4} ({len(batch_functions)} funciones):")
        
        for func_name, line_num in batch_functions:
            pkg, role = categorize_function(func_name)
            end_line = estimate_function_size(content, func_name, line_num - 1)
            
            # Generar tag de especificación
            tag = f"# pkg: {pkg} | rol: {role} | cut: L{line_num}-L{end_line} | todo: Extract to {pkg}"
            
            log_entries.append({
                'batch': batch_num + 4,
                'function': func_name,
                'line': line_num,
                'package': pkg,
                'role': role,
                'tag': tag,
                'size_lines': end_line - line_num + 1
            })
            
            print(f"  {func_name:30} L{line_num:4} -> {pkg:12} | {role}")
    
    # Generar log de resultados
    with open(OUTPUT_LOG, 'w', encoding='utf-8') as f:
        f.write("# FASE 2 - AUTO TAGGING LOG\n\n")
        f.write(f"**Fecha:** {Path(__file__).stat().st_mtime}\n")
        f.write(f"**Total funciones procesadas:** {len(log_entries)}\n")
        f.write(f"**Total lotes:** {total_batches}\n\n")
        
        # Resumen por paquete
        pkg_summary = {}
        for entry in log_entries:
            pkg = entry['package']
            pkg_summary[pkg] = pkg_summary.get(pkg, 0) + 1
        
        f.write("## Resumen por Paquete\n\n")
        for pkg, count in sorted(pkg_summary.items()):
            f.write(f"- **{pkg}**: {count} funciones\n")
        
        f.write("\n## Funciones Procesadas\n\n")
        for entry in log_entries:
            f.write(f"### {entry['function']} (L{entry['line']})\n")
            f.write(f"- **Paquete:** {entry['package']}\n")
            f.write(f"- **Rol:** {entry['role']}\n") 
            f.write(f"- **Tamaño:** ~{entry['size_lines']} líneas\n")
            f.write(f"- **Tag:** `{entry['tag']}`\n\n")
    
    print(f"\n✅ COMPLETADO! Log guardado en: {OUTPUT_LOG}")
    print(f"📈 PROGRESO TOTAL:")
    print(f"   Etiquetadas: {len(TAGGED_FUNCTIONS) + len(log_entries)}")
    print(f"   Restantes: {170 - len(TAGGED_FUNCTIONS) - len(log_entries)}")

if __name__ == "__main__":
    main()