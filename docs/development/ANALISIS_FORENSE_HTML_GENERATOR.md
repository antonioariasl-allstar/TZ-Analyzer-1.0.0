# 🧬 ANÁLISIS FORENSE ULTRA-PROFUNDO: HTML GENERATOR

**Fecha**: 27 de octubre de 2025  
**Objetivo**: Mapear TODAS las dependencias de `generar_informe_html` para extracción segura  
**Líneas analizadas**: 3207-5790 (2,583 líneas)  

---

## 🔍 **DEPENDENCIAS CRÍTICAS IDENTIFICADAS**

### 📚 **LIBRERÍAS EXTERNAS**
```python
# Librerías estándar Python
import json, math, os, re, shutil, sys, unicodedata
import logging, traceback, io, base64
from collections import Counter, defaultdict
from datetime import datetime, timedelta, time as _time
from typing import Any, Dict, List, Optional

# Librerías de datos
import numpy as np
import pandas as pd

# Librerías especializadas  
from simplekml import Kml
import simplekml as sk  # usado en funciones auxiliares

# Módulos locales
from utilidades import seleccionar_archivo, seleccionar_carpeta
from validaciones import validar_datos, guardar_errores
from kml_generador import generar_kml_puntos_libres
from tz_core.config_manager import cfg_build_rename_map
from tz_core.text_utils import normalizar_texto, normalizar_columnas_texto
```

### 🌐 **VARIABLES GLOBALES CRÍTICAS**
```python
# Variables ultra-críticas
CONFIG          # Configuración global del sistema
RENAME_MAP      # Mapa de sinónimos de columnas
_REUSABLE_STYLES  # Cache de estilos KML

# Variables de logging  
log()           # Función de logging global (usada 6+ veces en la función)
print()         # Salidas de debug y usuario
```

### 🛠️ **FUNCIONES AUXILIARES INTERNAS** (12 identificadas)
```python
def _fmt_dt(ts):                    # Formato fecha/hora
def _first_nonempty_in(df, cols):   # Primer valor no vacío en columnas
def _nunique_in(df, cols):          # Contar únicos en columnas
def _unique_values_in(df, cols):    # Valores únicos con límite
def _fmt_imei_item(x):              # Formato IMEI
def _row_html(label, single, n):    # Generar fila HTML
def _luhn_check(num):               # Validación Luhn para IMEI
def _is_valid_imei(val):            # Validador IMEI completo
# + 4 funciones auxiliares más detectadas en líneas posteriores
```

### 📋 **COLUMNAS CANÓNICAS USADAS**
```python
# Grupos de columnas sinónimas manejadas
tel_cols    = ["tel","telefono","numero","msisdn","a_number"]
alias_cols  = ["alias","alias_usuario","apodo"] 
user_cols   = ["usuario","nombre_usuario","suscriptor"]
abon_cols   = ["abonado","titular","owner","subscriber"]
imei_cols   = ["imei","imei1","imei_1"]
imsi_cols   = ["imsi","imsi1","imsi_1","imsi_origen"]
```

---

## 🎯 **SECCIONES HTML IDENTIFICADAS** (8 módulos)

1. **HTML-INTERACCIONES-1**: Tabla de interacciones principales
2. **HTML-TOC-1**: Tabla de contenidos y navegación  
3. **HTML-BRANDING-1**: Header y branding del reporte
4. **HTML-TABLA-ESPACIADO-1**: Estilos y espaciado de tablas
5. **HTML-ANTENAS-SIMPLE-1**: Lista simple de antenas
6. **HTML-ANTENAS-RANGOS-1**: Antenas con rangos de fechas
7. **HTML-HISTORIAL-CAMBIOS-1**: Cambios temporales
8. **HTML-HEATMAP-1**: Mapas de calor por día

---

## ⚠️ **RIESGOS IDENTIFICADOS**

### 🔴 **RIESGO ALTO**
- **Variables globales**: CONFIG y RENAME_MAP son críticas
- **Funciones auxiliares**: 12+ funciones internas interdependientes
- **Logging**: Sistema de log usado extensivamente
- **Estado compartido**: Cache de estilos reutilizables

### 🟠 **RIESGO MEDIO**  
- **Imports locales**: Dependencias de tz_core, utilidades, validaciones
- **Formato de datos**: Lógica compleja de columnas sinónimas
- **Generación KML**: Integración con simplekml

### 🟢 **RIESGO BAJO**
- **Librerías estándar**: json, os, datetime (bien aisladas)
- **Pandas/numpy**: Operaciones estándar de DataFrame

---

## 📊 **MÉTRICAS DE COMPLEJIDAD**

| Métrica | Valor | Estado |
|---------|-------|--------|
| **Líneas totales** | 2,583 | 🔴 EXTREMO |
| **Funciones internas** | 12+ | 🔴 ALTO |
| **Variables globales** | 4 críticas | 🟠 MEDIO |
| **Imports externos** | 15+ | 🟠 MEDIO |
| **Secciones HTML** | 8 módulos | 🟢 MANEJABLE |

---

## 🎖️ **RECOMENDACIONES TÁCTICAS**

### ✅ **ESTRATEGIA SEGURA**
1. **Extraer funciones auxiliares PRIMERO** (menor riesgo)
2. **Modularizar secciones HTML una a una** (commits atómicos)
3. **Mantener variables globales** hasta el final
4. **Testing continuo** después de cada extracción

### 🚨 **PUNTOS DE VIGILANCIA**
- ❗ **CONFIG**: No mover hasta que todas las funciones estén extraídas
- ❗ **Helper functions**: Extraer en grupo para evitar dependencias rotas  
- ❗ **Logging**: Mantener función `log()` accesible en todos los módulos
- ❗ **RENAME_MAP**: Crítico para mapeo de columnas

---

## 🎯 **SIGUIENTES PASOS**

1. **CREAR**: `tz_core/html_helpers.py` para funciones auxiliares
2. **EXTRAER**: `_fmt_dt`, `_first_nonempty_in`, etc. → helpers
3. **MODULARIZAR**: Cada sección HTML → función independiente  
4. **INTEGRAR**: Sistema de imports y configuración modular
5. **VALIDAR**: Tests E2E tras cada extracción

---

**🏆 CONCLUSIÓN**: El monstruo de 2,583 líneas es **EXTRAÍBLE** pero requiere **MÁXIMA PRECISIÓN**. 

Dependencias mapeadas ✅  
Riesgos identificados ✅  
Plan de batalla refinado ✅  

**¿PROCEDEMOS CON LA EXTRACCIÓN?** 🚀