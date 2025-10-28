#!/usr/bin/env python3
"""
Análisis de dependencias del monolito
Mapea TODAS las conexiones entre funciones para entender la "pita enredada"
"""

import re
import ast
from pathlib import Path
from collections import defaultdict
import json

def extraer_funciones(archivo):
    """Extrae todas las definiciones de funciones y sus líneas"""
    with open(archivo, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    funciones = {}
    for match in re.finditer(r'^(def|class)\s+(\w+)\s*\(', contenido, re.MULTILINE):
        tipo = match.group(1)
        nombre = match.group(2)
        linea = contenido[:match.start()].count('\n') + 1
        funciones[nombre] = {'tipo': tipo, 'linea': linea, 'llamadas': set()}
    
    return funciones, contenido

def analizar_llamadas(contenido, funciones):
    """Analiza qué funciones llaman a otras"""
    # Obtener bloques de cada función
    lineas = contenido.split('\n')
    
    for nombre_func, info in funciones.items():
        linea_inicio = info['linea'] - 1
        
        # Encontrar siguiente función para delimitar
        siguiente_linea = len(lineas)
        for otro_nombre, otra_info in funciones.items():
            if otro_nombre != nombre_func and otra_info['linea'] > info['linea']:
                if otra_info['linea'] < siguiente_linea:
                    siguiente_linea = otra_info['linea'] - 1
        
        # Analizar cuerpo de la función
        cuerpo = '\n'.join(lineas[linea_inicio:siguiente_linea])
        
        # Buscar llamadas a otras funciones
        for otra_func in funciones.keys():
            if otra_func != nombre_func:
                # Buscar llamadas directas
                patron = rf'\b{otra_func}\s*\('
                if re.search(patron, cuerpo):
                    info['llamadas'].add(otra_func)

def analizar_imports_externos(contenido):
    """Detecta imports y dependencias externas"""
    imports = set()
    
    # Imports estándar
    for match in re.finditer(r'^import\s+([\w.]+)', contenido, re.MULTILINE):
        imports.add(match.group(1))
    
    # From imports
    for match in re.finditer(r'^from\s+([\w.]+)\s+import', contenido, re.MULTILINE):
        imports.add(match.group(1))
    
    return imports

def encontrar_puntos_entrada(funciones):
    """Identifica funciones que son puntos de entrada (no llamadas por otras)"""
    todas = set(funciones.keys())
    llamadas_por_otras = set()
    
    for info in funciones.values():
        llamadas_por_otras.update(info['llamadas'])
    
    puntos_entrada = todas - llamadas_por_otras
    return puntos_entrada

def encontrar_funciones_huerfanas(funciones):
    """Funciones que no llaman a nada ni son llamadas por nadie"""
    todas = set(funciones.keys())
    llamadas_por_otras = set()
    que_llaman_algo = set()
    
    for nombre, info in funciones.items():
        if info['llamadas']:
            que_llaman_algo.add(nombre)
        llamadas_por_otras.update(info['llamadas'])
    
    huerfanas = todas - llamadas_por_otras - que_llaman_algo
    return huerfanas

def calcular_profundidad_dependencias(funciones, nombre, visitados=None):
    """Calcula cuántos niveles de dependencias tiene una función"""
    if visitados is None:
        visitados = set()
    
    if nombre in visitados:
        return 0  # Evitar ciclos
    
    visitados.add(nombre)
    
    if nombre not in funciones:
        return 0
    
    llamadas = funciones[nombre]['llamadas']
    if not llamadas:
        return 0
    
    profundidades = [calcular_profundidad_dependencias(funciones, llamada, visitados.copy()) 
                     for llamada in llamadas]
    
    return 1 + max(profundidades) if profundidades else 0

def identificar_funciones_criticas(funciones):
    """Funciones que son llamadas por muchas otras (núcleos críticos)"""
    contador_llamadas = defaultdict(int)
    
    for info in funciones.values():
        for llamada in info['llamadas']:
            contador_llamadas[llamada] += 1
    
    # Ordenar por número de dependientes
    criticas = sorted(contador_llamadas.items(), key=lambda x: x[1], reverse=True)
    return criticas

def main():
    archivo = "script_principal_bitacoras_refactory.py"
    print(f"🔬 ANÁLISIS FORENSE DE DEPENDENCIAS")
    print(f"{'='*60}\n")
    
    print(f"📂 Analizando: {archivo}")
    funciones, contenido = extraer_funciones(archivo)
    print(f"✅ Encontradas: {len(funciones)} funciones/clases\n")
    
    print("🔍 Analizando llamadas entre funciones...")
    analizar_llamadas(contenido, funciones)
    print("✅ Análisis de llamadas completo\n")
    
    # Convertir sets a listas para JSON
    funciones_json = {}
    for nombre, info in funciones.items():
        funciones_json[nombre] = {
            'tipo': info['tipo'],
            'linea': info['linea'],
            'llamadas': sorted(list(info['llamadas'])),
            'num_llamadas': len(info['llamadas'])
        }
    
    # REPORTE 1: Funciones críticas
    print("🎯 FUNCIONES CRÍTICAS (más dependientes)")
    print("-" * 60)
    criticas = identificar_funciones_criticas(funciones)[:15]
    for nombre, count in criticas:
        print(f"  {nombre:40s} → {count:3d} funciones dependen de ella")
    
    # REPORTE 2: Puntos de entrada
    print(f"\n🚪 PUNTOS DE ENTRADA (no llamadas por otras)")
    print("-" * 60)
    entradas = encontrar_puntos_entrada(funciones)
    for nombre in sorted(entradas)[:20]:
        profundidad = calcular_profundidad_dependencias(funciones, nombre)
        print(f"  {nombre:40s} → profundidad: {profundidad}")
    print(f"  Total: {len(entradas)} funciones")
    
    # REPORTE 3: Funciones con más dependencias
    print(f"\n🕸️  FUNCIONES MÁS ENREDADAS (más llamadas)")
    print("-" * 60)
    enredadas = sorted(funciones.items(), key=lambda x: len(x[1]['llamadas']), reverse=True)[:15]
    for nombre, info in enredadas:
        print(f"  {nombre:40s} → llama a {len(info['llamadas']):3d} funciones")
    
    # REPORTE 4: Imports externos
    print(f"\n📦 DEPENDENCIAS EXTERNAS")
    print("-" * 60)
    imports = analizar_imports_externos(contenido)
    for imp in sorted(imports):
        print(f"  - {imp}")
    
    # REPORTE 5: Funciones huérfanas
    print(f"\n👻 FUNCIONES HUÉRFANAS (candidatas a eliminar)")
    print("-" * 60)
    huerfanas = encontrar_funciones_huerfanas(funciones)
    for nombre in sorted(huerfanas)[:10]:
        print(f"  - {nombre} (línea {funciones[nombre]['linea']})")
    print(f"  Total: {len(huerfanas)} funciones")
    
    # REPORTE 6: Estadísticas generales
    print(f"\n📊 ESTADÍSTICAS GENERALES")
    print("-" * 60)
    total_conexiones = sum(len(info['llamadas']) for info in funciones.values())
    promedio = total_conexiones / len(funciones) if funciones else 0
    print(f"  Total funciones/clases: {len(funciones)}")
    print(f"  Total conexiones: {total_conexiones}")
    print(f"  Promedio llamadas por función: {promedio:.2f}")
    print(f"  Puntos de entrada: {len(entradas)}")
    print(f"  Funciones huérfanas: {len(huerfanas)}")
    
    # Guardar análisis completo en JSON
    reporte = {
        'total_funciones': len(funciones),
        'total_conexiones': total_conexiones,
        'promedio_llamadas': promedio,
        'funciones_criticas': [{'nombre': n, 'dependientes': c} for n, c in criticas],
        'puntos_entrada': sorted(list(entradas)),
        'funciones_huerfanas': sorted(list(huerfanas)),
        'funciones': funciones_json,
        'imports_externos': sorted(list(imports))
    }
    
    with open('tools/reporte_dependencias.json', 'w', encoding='utf-8') as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Reporte completo guardado en: tools/reporte_dependencias.json")
    print(f"\n{'='*60}")
    print("✅ Análisis completo")

if __name__ == '__main__':
    main()
