# TODO — TZ Analyzer v1.0.0

## 🔧 Friction points del wizard (priorizados)

Identificados durante pruebas de usabilidad. En orden de prioridad:

- [x] **F7** — ✅ Descartado — IMEI aparece como campo esencial del wizard
- [x] **F9** — ✅ Descartado — artefactos provenían del Excel original de la operadora, no del sistema
- [ ] **F2** — Columna de fecha sin hora asignada simultáneamente a fecha y hora sin advertencia
- [ ] **F3** — Columna asignada a dos campos: el aviso no orienta ni ofrece remediación
- [x] **F6** — ✅ Cerrado — opción R=Remapear documentada y testeada
- [ ] **F5-UX** — Ajuste cosmético: `F <valor fijo>` no muestra un ejemplo concreto
- [ ] **F8** — Ajuste cosmético: el prompt dice “Nombre base del KML”, aunque controla todos los archivos generados
- [x] **F10** — ✅ Mitigado — la lista de columnas puede consultarse durante el mapeo mediante `? ver columnas`

---

## 🧪 Deuda técnica conocida

- [x] **Aliases `_`-prefijados en producción** — ✅ Cerrado (cd4ec85) — migración completada

- [x] **README del repo** — ✅ Actualizado (Agosto 2026)

---

## 📊 Mejoras al informe HTML

**✅ Patrón Versión B cerrado** — omisión silenciosa reemplazada por declaraciones explícitas en secciones 1, 4, 5, 6, 7, 9, 10.

Pendientes (no bloqueantes — diferibles a v1.2):
- [ ] Hacer el informe más interpretativo y forenses defensible (requiere P0-A para separar voz/SMS/datos)
- [ ] Resumen analítico automático al inicio del informe
- [ ] Indicador de calidad de datos
- [ ] Tarjetas resumen por sección
- [ ] Resaltado de valores relevantes
- [ ] Índice navegable
- [ ] Tablas largas colapsables

---

## 🗺️ Decisión estratégica v1.1

✅ Camino adoptado de facto: **v1.1-Nacional** — validación y mejoras sobre bitácoras de formato salvadoreño. Decisión adoptada durante la implementación sin documento formal de cierre.

---

## 🔭 Horizonte (sin fecha)

- [ ] Exportación a IBM i2 / Gephi
- [ ] Manual técnico en PDF
- [ ] Empaquetado ejecutable (PyInstaller)
- [ ] Google Pinpoint — acceso solicitado, sin respuesta
- [ ] "Mente maestra" — herramienta de gestión de casos (proyecto separado)