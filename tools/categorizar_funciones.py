#!/usr/bin/env python3
"""
Categorizador de funciones - Identifica grupos lógicos
Para entender cómo desenredar la pita sin romperla
"""

import json
import re
from pathlib import Path

def leer_reporte():
    with open('tools/reporte_dependencias.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def categorizar_por_nombre_y_patron(funciones_json):
    """Categoriza funciones por patrones en nombres y contenido"""
    
    categorias = {
        'CONFIG': [],           # Manejo de configuración
        'KML': [],              # Generación de KML/geo
        'HTML': [],             # Generación de reportes HTML
        'NORMALIZACION': [],    # Limpieza y normalización de datos
        'VALIDACION': [],       # Validación de datos
        'TIEMPO': [],           # Manejo de fechas/horas
        'UI': [],               # Interfaz de usuario/menú
        'IO': [],               # Entrada/salida de archivos
        'UTILIDADES': [],       # Helpers genéricos
        'ANALISIS': [],         # Análisis de datos (antenas, contactos)
        'ORQUESTACION': [],     # Coordinación de flujo principal
        'GEO': [],              # Cálculos geográficos
        'HASH': [],             # Criptografía/hashing
    }
    
    patrones = {
        'CONFIG': [r'config', r'cfg_', r'bootstrap', r'get_config', r'synonym'],
        'KML': [r'kml', r'_crear_feature', r'generar_kml', r'compactar_nombre'],
        'HTML': [r'html', r'informe', r'seccion', r'construir_seccion'],
        'NORMALIZACION': [r'normalizar', r'_fix_mojibake', r'_dedupe', r'_aplicar_reemplazos'],
        'VALIDACION': [r'validar', r'wizard.*qc', r'preflight', r'esenciales'],
        'TIEMPO': [r'hhmmss', r'_en_rango', r'clasificar_rango', r'fecha', r'hora', r'minutes', r'time'],
        'UI': [r'solicitar', r'wizard', r'_modo_manual', r'seleccionar', r'menu'],
        'IO': [r'cargar', r'escribe', r'copiar.*logo', r'_sha256', r'atomic_write', r'hojas'],
        'GEO': [r'grados.*radianes', r'calcular_punto', r'generar_cono', r'azimut', r'lat', r'lon'],
        'HASH': [r'sha256', r'hash'],
        'ANALISIS': [r'analizar', r'historial.*cambios', r'interacciones', r'contactos'],
        'ORQUESTACION': [r'^main$', r'^run_', r'_modo_manual'],
    }
    
    for nombre, info in funciones_json.items():
        categorizado = False
        for categoria, patrones_lista in patrones.items():
            for patron in patrones_lista:
                if re.search(patron, nombre, re.IGNORECASE):
                    categorias[categoria].append({
                        'nombre': nombre,
                        'linea': info['linea'],
                        'llamadas': info['num_llamadas'],
                        'es_llamada_por': 0  # Lo calcularemos después
                    })
                    categorizado = True
                    break
            if categorizado:
                break
        
        if not categorizado:
            categorias['UTILIDADES'].append({
                'nombre': nombre,
                'linea': info['linea'],
                'llamadas': info['num_llamadas'],
                'es_llamada_por': 0
            })
    
    return categorias

def calcular_dependientes(categorias, reporte):
    """Cuenta cuántas funciones dependen de cada una"""
    # Construir mapa de dependientes
    dependientes = {}
    for nombre, info in reporte['funciones'].items():
        dependientes[nombre] = 0
    
    for nombre, info in reporte['funciones'].items():
        for llamada in info['llamadas']:
            if llamada in dependientes:
                dependientes[llamada] += 1
    
    # Actualizar categorías
    for categoria, funcs in categorias.items():
        for func in funcs:
            func['es_llamada_por'] = dependientes.get(func['nombre'], 0)
    
    return categorias

def identificar_nudos_criticos(categorias):
    """Identifica funciones que conectan múltiples categorías (nudos de la pita)"""
    nudos = []
    
    for categoria, funcs in categorias.items():
        for func in funcs:
            if func['es_llamada_por'] >= 2 and func['llamadas'] >= 2:
                nudos.append({
                    'nombre': func['nombre'],
                    'categoria': categoria,
                    'dependientes': func['es_llamada_por'],
                    'llama_a': func['llamadas'],
                    'score_nudo': func['es_llamada_por'] * func['llamadas']
                })
    
    return sorted(nudos, key=lambda x: x['score_nudo'], reverse=True)

def analizar_duplicados(reporte):
    """Encuentra funciones con nombres sospechosamente similares (posibles duplicados)"""
    nombres = list(reporte['funciones'].keys())
    duplicados = []
    
    for i, nombre1 in enumerate(nombres):
        for nombre2 in nombres[i+1:]:
            # Limpiar prefijos _ para comparar
            n1_clean = nombre1.lstrip('_')
            n2_clean = nombre2.lstrip('_')
            
            if n1_clean == n2_clean and nombre1 != nombre2:
                duplicados.append({
                    'func1': nombre1,
                    'linea1': reporte['funciones'][nombre1]['linea'],
                    'func2': nombre2,
                    'linea2': reporte['funciones'][nombre2]['linea']
                })
    
    return duplicados

def main():
    print("🧩 CATEGORIZACIÓN Y ANÁLISIS DE GRUPOS")
    print("="*70 + "\n")
    
    reporte = leer_reporte()
    
    print("📊 Categorizando funciones por dominio...")
    categorias = categorizar_por_nombre_y_patron(reporte['funciones'])
    categorias = calcular_dependientes(categorias, reporte)
    
    print("\n🗂️  DISTRIBUCIÓN POR CATEGORÍA")
    print("-"*70)
    for categoria, funcs in sorted(categorias.items(), key=lambda x: len(x[1]), reverse=True):
        if funcs:
            print(f"\n📁 {categoria} ({len(funcs)} funciones)")
            for func in sorted(funcs, key=lambda x: x['es_llamada_por'], reverse=True)[:5]:
                print(f"   {func['nombre']:35s} | deps:{func['es_llamada_por']:2d} | calls:{func['llamadas']:2d} | L{func['linea']}")
            if len(funcs) > 5:
                print(f"   ... y {len(funcs) - 5} más")
    
    print("\n\n⚠️  NUDOS CRÍTICOS (difíciles de desenredar)")
    print("-"*70)
    nudos = identificar_nudos_criticos(categorias)
    if nudos:
        for nudo in nudos[:10]:
            print(f"🔴 {nudo['nombre']:35s} [{nudo['categoria']}]")
            print(f"   └─ {nudo['dependientes']} funciones dependen | llama a {nudo['llama_a']} | score: {nudo['score_nudo']}")
    else:
        print("✅ No hay nudos críticos detectados")
    
    print("\n\n🔍 POSIBLES DUPLICADOS")
    print("-"*70)
    duplicados = analizar_duplicados(reporte)
    if duplicados:
        for dup in duplicados:
            print(f"⚠️  {dup['func1']} (L{dup['linea1']}) ≈ {dup['func2']} (L{dup['linea2']})")
    else:
        print("✅ No se detectaron duplicados obvios")
    
    # Guardar categorización
    resultado = {
        'categorias': {cat: [f['nombre'] for f in funcs] for cat, funcs in categorias.items()},
        'nudos_criticos': nudos,
        'duplicados': duplicados,
        'estadisticas': {
            cat: {
                'total': len(funcs),
                'promedio_dependientes': sum(f['es_llamada_por'] for f in funcs) / len(funcs) if funcs else 0,
                'promedio_llamadas': sum(f['llamadas'] for f in funcs) / len(funcs) if funcs else 0
            }
            for cat, funcs in categorias.items() if funcs
        }
    }
    
    with open('tools/categorizacion_funciones.json', 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    
    print(f"\n\n💾 Categorización guardada en: tools/categorizacion_funciones.json")
    
    # RECOMENDACIONES
    print("\n\n💡 RECOMENDACIONES DE ESTRATEGIA")
    print("="*70)
    print("""
1️⃣  FUNCIONES SEGURAS PARA MOVER (sin dependientes, pocas llamadas):
   → Buscar en categoría UTILIDADES con es_llamada_por=0

2️⃣  NUDOS CRÍTICOS A RESOLVER PRIMERO:
   → {nudos_principales}

3️⃣  CATEGORÍAS MÁS ENREDADAS:
   → Aquellas con promedio alto de dependientes

4️⃣  DUPLICADOS A LIMPIAR:
   → {num_duplicados} posibles duplicados detectados

5️⃣  ORDEN SUGERIDO DE EXTRACCIÓN:
   a) UTILIDADES (bajo riesgo)
   b) IO (entrada/salida - relativamente independiente)
   c) GEO (cálculos matemáticos puros)
   d) HASH (utilidades de hashing)
   e) TIEMPO (después de resolver dependencias circulares)
   f) NORMALIZACION (usado por muchos)
   g) VALIDACION (ídem)
   h) KML/HTML (muy enredados, dejar para último)
   i) ORQUESTACION (nunca mover main)
""".format(
        nudos_principales=', '.join([n['nombre'] for n in nudos[:3]]) if nudos else 'Ninguno',
        num_duplicados=len(duplicados)
    ))
    
    print("="*70)
    print("✅ Análisis de categorización completo\n")

if __name__ == '__main__':
    main()
