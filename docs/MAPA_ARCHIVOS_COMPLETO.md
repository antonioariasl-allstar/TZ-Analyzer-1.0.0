# 🗺️ MAPA COMPLETO DE ARCHIVOS - TZ ANALYZER

## 📍 GUÍA DEFINITIVA PARA DESARROLLADORES

### 🎯 PROPÓSITO
Este documento elimina **TODA CONFUSIÓN** sobre qué archivos usar, cuáles son esqueletos, y la estructura del proyecto. **Consultarlo SIEMPRE antes de modificar código.**

---

## 📂 ESTRUCTURA PRINCIPAL

### ✅ ARCHIVOS ACTIVOS (USAR ESTOS)

#### **🚀 ENTRY POINTS**
| Archivo | Propósito | Uso |
|---------|-----------|-----|
| **`run.py`** | 🟢 **Entry point principal** | `python run.py` para uso normal |
| **`script_principal_bitacoras_refactory.py`** | 🟢 **Motor principal** | Núcleo híbrido del sistema |

#### **🎨 INTERFAZ DE USUARIO**
| Archivo | Propósito | Funciones Principales |
|---------|-----------|----------------------|
| **`utilidades.py`** | 🟢 **UI Helpers activos** | `seleccionar_archivo()`, `seleccionar_carpeta()` |

#### **🔧 PROCESAMIENTO DE DATOS**
| Archivo | Propósito | Funciones Principales |
|---------|-----------|----------------------|
| **`validaciones.py`** | 🟢 **Sistema validación completo** | `validar_datos()`, `guardar_errores()` |
| **`kml_generador.py`** | 🟢 **Generación KML funcional** | `generar_kml_puntos_libres()`, `hex_to_abgr()` |

---

## 🏗️ FRAMEWORK MODULAR (tz_core/)

### ✅ MÓDULOS ACTIVOS
| Archivo | Estado | Propósito |
|---------|--------|-----------|
| **`tz_core/config_manager.py`** | 🟢 **ACTIVO** | Gestión configuración híbrida |
| **`tz_core/data_loader.py`** | 🟢 **ACTIVO** | Carga datos con sistema dual |
| **`tz_core/utils.py`** | 🟢 **ACTIVO** | Utilidades puras (hash, strings) |
| **`tz_core/html_generator.py`** | 🟢 **HÍBRIDO** | Redirección inteligente HTML |

### 🏗️ ESQUELETOS PREPARADOS
| Archivo | Estado | Propósito |
|---------|--------|-----------|
| **`tz_core/kml_generator.py`** | 🟡 **ESQUELETO** | Preparado para migración KML |
| **`tz_core/data_validator.py`** | 🟡 **ESQUELETO** | Preparado para migración validaciones |
| **`tz_core/data_processor.py`** | 🟡 **ESQUELETO** | Preparado para procesamiento |
| **`tz_core/ui_helpers.py`** | 🟡 **ESQUELETO** | Preparado para helpers UI |

---

## 🧪 TESTING Y AUTOMATION

### ✅ HERRAMIENTAS ESPECÍFICAS
| Archivo | Propósito | Uso |
|---------|-----------|-----|
| **`run_baseline_correct.py`** | 🔧 **Testing automation** | Captura baseline golden |
| **`capture_golden_baseline.py`** | 🔧 **Testing utilities** | Automatización testing |
| **`investigacion_forense.py`** | 🔧 **Debug tool** | Investigación de problemas |
| **`tests/test_e2e_regresion.py`** | 🧪 **E2E testing** | Validación completa |

---

## ⚠️ REGLAS CRÍTICAS

### 🚨 ANTES DE MODIFICAR CÓDIGO:

#### **1. ARCHIVOS ACTIVOS** 🟢
- ✅ **SÍ PUEDES** modificar y arreglar bugs
- ✅ **SÍ PUEDES** agregar funcionalidades
- ✅ **TESTING REQUERIDO** después de cambios

#### **2. ESQUELETOS** 🟡
- ❌ **NO MODIFICAR** sin planificación arquitectónica
- ❌ **NO USAR** en producción
- 🔄 **COORDINAR** migración con arquitectura híbrida

#### **3. IMPORTS CRÍTICOS**
```python
# ✅ CORRECTO - Usar archivos activos
from utilidades import seleccionar_archivo
from validaciones import validar_datos
from tz_core.utils import sha256_de_archivo

# ❌ INCORRECTO - Esqueletos vacíos
from tz_core.data_validator import DataValidator  # ESQUELETO
from tz_core.kml_generator import KMLGenerator    # ESQUELETO
```

---

## 🎯 DECISIONES RÁPIDAS

### **¿Qué archivo usar para...?**

| Necesidad | Archivo Correcto |
|-----------|------------------|
| **Ejecutar programa** | `run.py` |
| **Seleccionar archivos** | `utilidades.py` |
| **Validar datos** | `validaciones.py` |
| **Generar KML** | `kml_generador.py` |
| **Calcular hashes** | `tz_core/utils.py` |
| **Configuración** | `tz_core/config_manager.py` |
| **Testing automation** | `run_baseline_correct.py` |

### **¿Archivo duplicado o complementario?**

| Par de Archivos | Relación |
|-----------------|----------|
| `utilidades.py` vs `tz_core/utils.py` | 🤝 **COMPLEMENTARIOS** (UI vs Core) |
| `validaciones.py` vs `tz_core/data_validator.py` | 🔄 **ACTIVO vs ESQUELETO** |
| `kml_generador.py` vs `tz_core/kml_generator.py` | 🔄 **ACTIVO vs ESQUELETO** |
| `run.py` vs `run_baseline_correct.py` | 🤝 **COMPLEMENTARIOS** (Main vs Testing) |

---

## 🏗️ ARQUITECTURA HÍBRIDA

### **Filosofía del Sistema**
```
ARCHIVOS RAÍZ (Probados) ←→ FRAMEWORK MODULAR (Evolutivo)
        ↑                           ↑
   Código estable              Código modular
   Funcionalidad completa      Preparado para futuro
   Usado en producción         Esqueletos + híbridos
```

### **Evolución Futura**
1. **FASE ACTUAL**: Híbrido funcional al 100%
2. **MIGRACIÓN OPCIONAL**: Esqueletos → Funcionalidad
3. **DEPRECACIÓN GRADUAL**: Archivos raíz → Framework

---

## 📊 RESUMEN EJECUTIVO

### **ESTADO DEL PROYECTO** ✅
- **Sistema funcional** al 100%
- **Arquitectura híbrida** estable y escalable
- **Confusión eliminada** con documentación clara
- **Evolución planificada** sin breaking changes

### **PARA NUEVOS DESARROLLADORES** 🎯
1. **LEE ESTE DOCUMENTO** antes de modificar código
2. **USA ARCHIVOS ACTIVOS** marcados con 🟢
3. **NO TOQUES ESQUELETOS** marcados con 🟡
4. **PREGUNTA SI DUDAS** antes de cambios arquitectónicos

### **MANTENIMIENTO** 🔧
- **Bugs**: Arreglar en archivos activos 🟢
- **Features**: Evaluar si van en raíz o framework
- **Testing**: Validar siempre con suite completa

---

**Fecha**: 26 de octubre de 2025  
**Versión**: TZ Analyzer v1.0.0  
**Arquitectura**: Híbrida Permanente  
**Estado**: Documentación completa sin ambigüedades

---

## 🎪 CONCLUSIÓN

**ZERO CONFUSIÓN GARANTIZADA.** Este documento elimina toda ambigüedad sobre la estructura del proyecto. Cualquier desarrollador puede identificar inmediatamente qué archivo usar para qué propósito.

**¡Bookmark este archivo y consúltalo siempre!** 🚀