# TODO — TZ Analyzer v1.0.0

## 🔧 Friction points del wizard (priorizados)

Identificados durante pruebas de usabilidad. En orden de prioridad:

- [ ] **F7** — Integración IMEI/Tel fuera del wizard (requiere consenso de flujo antes de implementar)
- [ ] **F9** — Artefactos de encoding en logs de debug en Windows (charset)
- [ ] **F2** — Datetime duplicado aceptado sin advertencia al usuario
- [ ] **F3** — Columna asignada dos veces sin feedback visible
- [ ] **F6** — Opción de remap no documentada en el wizard
- [ ] **F5** — Campo `F valor` sin ejemplo visible para el usuario
- [ ] **F8** — Prompt de cambio de nombre de archivo sin contexto suficiente
- [ ] **F10** — Inputs inválidos en prompts de confirmación (S/N/A, I/T/Enter) no se rechazan — el sistema cae silenciosamente a comportamiento por defecto sin avisar al usuario. Riesgo: analista cree haber cambiado selección cuando no ocurrió nada.

---

## 🧪 Deuda técnica conocida

- [ ] **Aliases `_`-prefijados en producción** — Migración pendiente a nombres públicos antes de eliminar:
  - `_pick_col` → usado en `interacciones_builder.py`, `script_principal`, `assembler.py`
  - `_coalesce_duplicates` → usado en `manual_flow.py`
  - `_solicitar_filtros_tiempo` / `_aplicar_filtros_tiempo` → `script_principal` ln 153/651
  - `_solicitar_overrides_topn` → `tests/helpers/monkeypatch_flow.py`
  - `_a_float` → `format_utils.py`

- [ ] **README del repo** — ✅ Actualizado (Mayo 2026)

---

## 📊 Mejoras al informe HTML

- [ ] Hacer el informe más interpretativo y forenses defensible
- [ ] Añadir advertencias visibles cuando datos son parciales o heterogéneos
- [ ] Evaluar separación de registros de datos móviles del análisis de voz/SMS

---

## 🗺️ Decisión estratégica v1.1

Tres caminos definidos — decisión pendiente:

- **Camino A** — Cerrar friction list (F2, F3, F5, F6, F7, F8, F9) sin abordar generalización de formatos
- **Camino B** — Atacar resolución de identidad de formato para soportar operadoras diversas
- **Camino C** *(recomendación actual)* — Realizar encuesta corta de formatos de operadoras salvadoreñas antes de decidir alcance

---

## 🔭 Horizonte (sin fecha)

- [ ] Exportación a IBM i2 / Gephi
- [ ] Manual técnico en PDF
- [ ] Empaquetado ejecutable (PyInstaller)
- [ ] Google Pinpoint — acceso solicitado, sin respuesta
- [ ] "Mente maestra" — herramienta de gestión de casos (proyecto separado)