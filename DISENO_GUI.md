# 🎨 DISEÑO DE INTERFAZ GRÁFICA (GUI) - TZ Analysis

**Fecha de planificación:** 21 de octubre de 2025  
**Estado:** 📋 PLANIFICACIÓN  
**Prioridad:** Alta (antes de empaquetar v1.0.0)

---

## 🎯 OBJETIVO

Reemplazar la interfaz de consola actual por una GUI moderna tipo **wizard/asistente** con navegación paso a paso (similar a importación de Excel o Google Earth Pro).

---

## 🛠️ TECNOLOGÍA ELEGIDA: CustomTkinter

### ✅ Razones de elección:

| Criterio | Evaluación |
|----------|------------|
| **Costo** | ✅ 100% GRATIS (Licencia MIT) |
| **Permanencia** | ✅ Open source, siempre será gratis |
| **Uso comercial** | ✅ Permitido sin restricciones |
| **Aspecto visual** | ✅ Moderno (tipo Windows 11) |
| **Curva de aprendizaje** | ✅ Fácil (basado en tkinter estándar) |
| **Tamaño empaquetado** | ✅ Ligero (~15-20 MB total) |
| **Multiplataforma** | ✅ Windows, Mac, Linux |
| **Mantenimiento** | ✅ Activo (16k+ stars en GitHub) |

**🔗 GitHub:** https://github.com/TomSchimansky/CustomTkinter  
**📦 Instalación:** `pip install customtkinter`

---

## 📐 ESTRUCTURA DE LA GUI

### Wizard de 5 pasos:

```
Paso 1: Selección de archivo Excel
   ↓
Paso 2: Mapeo de columnas esenciales
   ↓
Paso 3: Mapeo de campos opcionales
   ↓
Paso 4: Filtros y opciones (Top N, rangos temporales)
   ↓
Paso 5: Carpeta de salida y confirmación
   ↓
Pantalla de progreso con barra
   ↓
Pantalla de resultados con opciones
```

---

## 🖼️ MOCKUPS DE PANTALLAS

### **Paso 1: Selección de archivo**
```
┌─────────────────────────────────────────────┐
│  TZ Analysis - Asistente de Mapeo          │
├─────────────────────────────────────────────┤
│                                             │
│  [Paso 1 de 5] Selección de archivo        │
│                                             │
│  📁 Archivo Excel:                          │
│  [____________________________] [Examinar]  │
│                                             │
│  📊 Hoja detectada: "Hoja1"                 │
│  [Dropdown: Hoja1 ▼]                        │
│                                             │
│             [Cancelar]  [Siguiente >]       │
└─────────────────────────────────────────────┘
```

### **Paso 2: Mapeo de columnas esenciales**
```
┌─────────────────────────────────────────────┐
│  TZ Analysis - Asistente de Mapeo          │
├─────────────────────────────────────────────┤
│                                             │
│  [Paso 2 de 5] Mapeo de columnas esenciales│
│                                             │
│  Columnas detectadas en Excel:              │
│  ┌─────────────────────────────────────┐   │
│  │ TELEFONO | FECHA | HORA | LAT | ... │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Mapeo (selecciona de la lista):            │
│  Teléfono:  [Dropdown: TELEFONO ▼]         │
│  Fecha:     [Dropdown: FECHA ▼]            │
│  Hora:      [Dropdown: HORA ▼]             │
│  Latitud:   [Dropdown: LAT ▼]              │
│  Longitud:  [Dropdown: LON ▼]              │
│  Azimut:    [Dropdown: AZIMUT ▼]           │
│                                             │
│  ✓ Vista previa: 3 filas                   │
│                                             │
│        [< Atrás] [Cancelar] [Siguiente >]  │
└─────────────────────────────────────────────┘
```

### **Paso 3: Campos opcionales**
```
┌─────────────────────────────────────────────┐
│  TZ Analysis - Asistente de Mapeo          │
├─────────────────────────────────────────────┤
│                                             │
│  [Paso 3 de 5] Mapeo de campos opcionales  │
│                                             │
│  Alias:     [Dropdown: -Omitir- ▼]         │
│  Usuario:   [Dropdown: USUARIO ▼]          │
│  Abonado:   [Dropdown: -Omitir- ▼]         │
│  IMEI:      [Dropdown: IMEI ▼]             │
│  Contacto:  [Dropdown: DESTINO ▼]          │
│  Duración:  [Dropdown: DURACION ▼]         │
│                                             │
│  O ingresa un valor fijo:                   │
│  Alias: [___________________]               │
│                                             │
│        [< Atrás] [Cancelar] [Siguiente >]  │
└─────────────────────────────────────────────┘
```

### **Paso 4: Filtros y opciones**
```
┌─────────────────────────────────────────────┐
│  TZ Analysis - Asistente de Mapeo          │
├─────────────────────────────────────────────┤
│                                             │
│  [Paso 4 de 5] Filtros y opciones          │
│                                             │
│  Tipo de filtro:                            │
│  ○ Sin filtro (toda la bitácora)           │
│  ○ Día específico: [__/__/____]            │
│  ○ Rango de días: De[__/__/____]A[__/__/___]│
│  ○ Rango horario: De[__:__]A[__:__]        │
│                                             │
│  Top de antenas:  [10 ▼]                   │
│  Top de contactos: [10 ▼]                   │
│                                             │
│  Color tema:                                │
│  [Paleta ▼] o ingresa HEX: [#______]       │
│                                             │
│        [< Atrás] [Cancelar] [Siguiente >]  │
└─────────────────────────────────────────────┘
```

### **Paso 5: Carpeta de salida**
```
┌─────────────────────────────────────────────┐
│  TZ Analysis - Asistente de Mapeo          │
├─────────────────────────────────────────────┤
│                                             │
│  [Paso 5 de 5] Carpeta de salida           │
│                                             │
│  📁 Guardar resultados en:                  │
│  [____________________________] [Examinar]  │
│                                             │
│  Nombre base: [bitacora_2025_10_21____]    │
│                                             │
│  Archivos a generar:                        │
│  ☑ KML/KMZ                                  │
│  ☑ Informe HTML                             │
│  ☑ Archivo de errores (si hay)             │
│  ☑ Archivo de hashes SHA-256               │
│                                             │
│        [< Atrás] [Cancelar]  [Procesar]    │
└─────────────────────────────────────────────┘
```

### **Pantalla de progreso**
```
┌─────────────────────────────────────────────┐
│  TZ Analysis - Procesando...               │
├─────────────────────────────────────────────┤
│                                             │
│  ████████████████░░░░░░░░░ 65%             │
│                                             │
│  ✓ Archivo cargado                          │
│  ✓ Datos validados (1,250 registros)       │
│  → Generando KML...                         │
│    Generando HTML...                        │
│    Creando archivos de hash...              │
│                                             │
│  Tiempo estimado: 15 segundos               │
│                                             │
│                    [Cancelar]               │
└─────────────────────────────────────────────┘
```

### **Pantalla de resultados**
```
┌─────────────────────────────────────────────┐
│  TZ Analysis - ¡Proceso completo!          │
├─────────────────────────────────────────────┤
│                                             │
│  ✓ Archivos generados exitosamente:        │
│                                             │
│  📁 C:\Salida\bitacora_2025_10_21\         │
│    ├─ bitacora_2025_10_21_mapeo.kmz       │
│    ├─ bitacora_2025_10_21_informe.html    │
│    ├─ bitacora_2025_10_21_errores.txt     │
│    └─ bitacora_2025_10_21_hashes.txt      │
│                                             │
│  📊 Resumen:                                 │
│    • Registros procesados: 1,250           │
│    • Antenas únicas: 47                    │
│    • Periodo: 15/10/2025 - 20/10/2025      │
│                                             │
│  [Abrir carpeta] [Nuevo análisis] [Cerrar] │
└─────────────────────────────────────────────┘
```

---

## 🎨 COMPONENTES Y CARACTERÍSTICAS

### Elementos visuales:
- ✅ **Dropdowns** para mapeo de columnas
- ✅ **File dialogs** para selección de archivos/carpetas
- ✅ **Radio buttons** para opciones excluyentes
- ✅ **Checkboxes** para opciones múltiples
- ✅ **Progress bar** animada durante procesamiento
- ✅ **Botones** estilo moderno: Siguiente, Atrás, Cancelar
- ✅ **Labels** con iconos (📁, 📊, ✓, →)
- ✅ **Preview** de datos (primeras 3 filas)

### Funcionalidades:
- ✅ Navegación: Siguiente/Atrás entre pasos
- ✅ Validación en tiempo real (campos obligatorios)
- ✅ Autodetección de columnas con IA/heurística
- ✅ Guardado de configuración (para reutilizar mapeo)
- ✅ Mensajes de error claros y amigables
- ✅ Tooltips con ayuda contextual
- ✅ Atajos de teclado (Enter=Siguiente, Esc=Cancelar)

---

## 📂 ESTRUCTURA DE ARCHIVOS SUGERIDA

```
TZ_Analysis_1.0.0_REPO/
│
├── script_principal_bitacoras_refactory.py  # Motor (backend)
├── validaciones.py                          # Validación de datos
├── utilidades.py                            # Utilidades
├── kml_generador.py                         # Generador KML
│
├── gui_app.py                               # ← NUEVO: Punto de entrada GUI
├── gui/                                     # ← NUEVO: Módulo GUI
│   ├── __init__.py
│   ├── main_window.py                       # Ventana principal
│   ├── wizard_steps.py                      # Definición de pasos
│   ├── step1_file_selection.py              # Paso 1
│   ├── step2_essential_mapping.py           # Paso 2
│   ├── step3_optional_mapping.py            # Paso 3
│   ├── step4_filters.py                     # Paso 4
│   ├── step5_output.py                      # Paso 5
│   ├── progress_window.py                   # Ventana progreso
│   ├── result_window.py                     # Ventana resultados
│   └── components/                          # Componentes reutilizables
│       ├── __init__.py
│       ├── column_mapper.py                 # Widget mapeo columnas
│       ├── file_picker.py                   # Widget selección archivos
│       └── preview_table.py                 # Widget preview datos
│
├── assets/                                  # ← NUEVO: Recursos visuales
│   ├── logo.png                             # Logo de la app
│   └── icon.ico                             # Icono del ejecutable
│
├── config.json                              # Configuración
├── requirements.txt                         # Dependencias (+ customtkinter)
└── README.md                                # Documentación
```

---

## 🚀 PLAN DE IMPLEMENTACIÓN

### **Fase 1: Prototipo básico (1 semana)**
- [ ] Instalar CustomTkinter en el entorno
- [ ] Crear ventana principal con navegación
- [ ] Implementar Paso 1 (selección de archivo)
- [ ] Implementar Paso 2 (mapeo esencial con dropdowns)
- [ ] Probar navegación Siguiente/Atrás

### **Fase 2: Funcionalidad completa (1-2 semanas)**
- [ ] Implementar Paso 3 (campos opcionales)
- [ ] Implementar Paso 4 (filtros y opciones)
- [ ] Implementar Paso 5 (carpeta salida)
- [ ] Conectar GUI con motor existente (backend)
- [ ] Implementar barra de progreso
- [ ] Implementar pantalla de resultados

### **Fase 3: Pulido y testing (3-5 días)**
- [ ] Agregar validaciones en tiempo real
- [ ] Mensajes de error amigables
- [ ] Iconos y branding (Logo TZ)
- [ ] Tooltips de ayuda
- [ ] Testing exhaustivo de flujos
- [ ] Manejo de casos extremos

### **Fase 4: Empaquetado (2-3 días)**
- [ ] Configurar PyInstaller
- [ ] Crear ejecutable Windows
- [ ] Probar en máquina limpia
- [ ] Documentación de uso
- [ ] Instalador opcional (NSIS o Inno Setup)

**⏱️ Tiempo estimado total: 3-4 semanas**

---

## 🔧 DEPENDENCIAS ADICIONALES

Actualizar `requirements.txt`:
```txt
# Existentes
et_xmlfile==2.0.0
lxml==6.0.2
numpy==2.3.4
openpyxl==3.1.5
pandas==2.2.2
pillow==12.0.0
python-dateutil==2.9.0.post0
python-pptx==0.6.23
pytz==2025.2
simplekml==1.3.6
six==1.17.0
tzdata==2025.2
xlsxwriter==3.2.9

# NUEVAS (para GUI)
customtkinter==5.2.2  # GUI moderna
Pillow>=10.0.0        # Manejo de imágenes (ya incluido, actualizar)
```

---

## 💡 CARACTERÍSTICAS AVANZADAS (Futuro)

### Versión 1.1+:
- [ ] **Drag & Drop** de archivos (arrastrar Excel a la ventana)
- [ ] **Autodetección inteligente** de columnas con ML
- [ ] **Guardado de perfiles** de mapeo (reutilizar configuraciones)
- [ ] **Modo oscuro** (dark mode)
- [ ] **Multi-idioma** (español/inglés)
- [ ] **Exportación a múltiples formatos** (además de KML)
- [ ] **Vista previa 3D** del mapa antes de generar
- [ ] **Integración con Google Maps API** (opcional)

---

## 📝 NOTAS IMPORTANTES

### Compatibilidad:
- ✅ La GUI NO reemplaza el motor actual
- ✅ El código de consola se mantiene como backend
- ✅ GUI llama a las funciones existentes
- ✅ Separación clara: GUI (frontend) ↔ Motor (backend)

### Empaquetado:
- Para PyInstaller, se necesitará un `.spec` file especial
- CustomTkinter requiere incluir sus archivos de tema
- Logo TZ debe empaquetarse como recurso
- Tamaño final estimado: ~20-25 MB (Windows)

### Testing:
- Probar en Windows 10 y 11
- Validar con archivos Excel de diferentes tamaños
- Casos extremos: archivos corruptos, cancelación de proceso
- Validar que errores se muestren amigablemente

---

## 🎯 CRITERIOS DE ÉXITO

La GUI estará lista para producción cuando:
- ✅ Todos los 5 pasos funcionen correctamente
- ✅ Navegación Siguiente/Atrás sin errores
- ✅ Validaciones en tiempo real funcionando
- ✅ Barra de progreso muestra avance real
- ✅ Manejo de errores sin crashes
- ✅ Se genera correctamente KML/KMZ/HTML
- ✅ Ejecutable empaquetado funciona en máquina limpia
- ✅ Usuario puede completar flujo sin ayuda

---

## 📚 RECURSOS Y REFERENCIAS

### Documentación:
- **CustomTkinter Docs:** https://customtkinter.tomschimansky.com/
- **CustomTkinter GitHub:** https://github.com/TomSchimansky/CustomTkinter
- **Ejemplos:** https://github.com/TomSchimansky/CustomTkinter/tree/master/examples

### Empaquetado:
- **PyInstaller Docs:** https://pyinstaller.org/en/stable/
- **CustomTkinter + PyInstaller:** https://github.com/TomSchimansky/CustomTkinter/wiki/Packaging

### Inspiración de diseño:
- Google Earth Pro (importación de datos)
- Excel (asistente de importación de texto)
- Windows 11 Settings (estética moderna)

---

## 👤 AUTOR

**Tony (Omar Arias)**  
**Proyecto:** TZ Analysis 1.0.0  
**Fecha de diseño:** 21 de octubre de 2025  
**Estado:** Planificación completa - Listo para implementar

---

## 📌 PRÓXIMOS PASOS

**Cuando estés listo para comenzar la GUI:**

1. Abrir este archivo (`DISENO_GUI.md`)
2. Instalar CustomTkinter: `pip install customtkinter`
3. Crear rama nueva: `git checkout -b feature/gui-wizard`
4. Comenzar con Fase 1 (prototipo básico)
5. Hacer commits incrementales
6. Testing continuo
7. Merge a main cuando esté probado

**¡Esta semilla está lista para madurar!** 🌱→🌳
