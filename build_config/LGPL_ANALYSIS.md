# simplekml (LGPLv3+) — análisis de empaquetado y opción aplicable del Art. 4

Documento de apoyo para el componente `simplekml` del manifiesto
`build_config/third_party_components.json` (bloque P1-LICENSES). No es
asesoría jurídica; es un registro técnico de evidencia local para que quien
tome la decisión de distribuir externamente copias de TZ Analyzer cuente con
los hechos verificados.

## A. Empaquetado real dentro del ONEDIR/PYZ

`simplekml` es un paquete 100% Python puro (sin extensiones C). PyInstaller
lo detecta y compila junto con el resto de módulos Python de la aplicación
directamente dentro de `build/TZ_Analyzer/PYZ-00.pyz` (archivo zip de
bytecode). Evidencia: `build/TZ_Analyzer/PYZ-00.toc` lista
`simplekml`, `simplekml.kml`, `simplekml.base`, etc. como módulos embebidos.
No existe una carpeta `simplekml/` suelta en `dist/TZ Analyzer/_internal/`:
a diferencia de numpy, pandas, PIL o lxml (que sí se extraen como directorios
por tener datos o extensiones nativas), simplekml viaja únicamente como
bytecode dentro del blob `PYZ-00.pyz`, indistinguible en el disco del código
propio de TZ Analyzer.

## B. ¿Es reemplazable como módulo separado?

No de forma soportada. No hay una carpeta `simplekml/` externa que un
usuario pueda sustituir por una versión modificada (como sí ocurre, por
ejemplo, con `tz_core/assets/vendor/leaflet/`, que es un directorio de
archivos sueltos). Sustituir `simplekml` requeriría desempaquetar
`PYZ-00.pyz`, reemplazar el bytecode del módulo y volver a empaquetar — no
es un mecanismo documentado, soportado ni razonablemente accesible para un
usuario final del ejecutable distribuido.

## C. Opción del Art. 4 de la LGPLv3 aplicable

El Art. 4 (Combined Works) exige, entre otras condiciones (a-c ya
satisfechas por incluir aviso + texto de la licencia en
`THIRD-PARTY-NOTICES.txt`), elegir **una** de estas dos vías (4d):

- **4d1 — "Suitable shared library mechanism"**: requiere que en tiempo de
  ejecución se use una copia de la Library ya presente en el sistema del
  usuario, reemplazable por una versión modificada interface-compatible.
  **No aplica**: simplekml no se carga desde un mecanismo de enlace
  dinámico del sistema operativo ni desde una copia externa al ejecutable;
  está embebido en el mismo blob de bytecode que el resto de la app (ver A
  y B).

- **4d0 — Minimal Corresponding Source + Corresponding Application Code**:
  acompañar el Minimal Corresponding Source de la Library (el código fuente
  de simplekml, ya público bajo LGPLv3+ en PyPI/GitHub) y el Corresponding
  Application Code en una forma que permita al usuario recombinar o
  re-enlazar la Application con una versión modificada de simplekml, en la
  manera especificada por el Art. 6 de la GPL para transmitir Corresponding
  Source (incluye la opción de una oferta escrita válida por el período
  requerido). **Es la opción aplicable** por descarte de 4d1.

## D. Material que habría que proporcionar

Por eliminación de 4d1, para cumplir 4d0 antes de entregar copias externas
del ejecutable compilado se necesita, además de lo que este bloque P1 ya
resuelve (aviso + texto LGPLv3 íntegro en THIRD-PARTY-NOTICES.txt):

1. El código fuente de simplekml en sí (Minimal Corresponding Source de la
   Library) — trivialmente disponible: es un paquete público en PyPI/GitHub
   bajo su propia LGPLv3+.
2. El "Corresponding Application Code" — es decir, el código y los
   materiales de build de TZ Analyzer en una forma que permita a quien
   recibe una copia recombinar o re-enlazar la aplicación con una versión
   modificada de simplekml y obtener un ejecutable funcional. Este
   repositorio (tz_core/, tz_web/, tz_launcher.py, requirements.txt,
   TZ_Analyzer.spec, tools/build_windows.py) ya constituye ese material y
   ya permite reconstruir el ejecutable cambiando la versión fijada de
   simplekml en requirements.txt y volviendo a correr
   `python -m tools.build_windows` — el mecanismo existe y funciona (así se
   produjo BUILD-2).
3. Lo que falta no es material técnico sino un **canal/compromiso de
   entrega**: que quien reciba copias del `.exe` (fuera del equipo de
   desarrollo) tenga efectivamente acceso a (1) y (2), ya sea entregando el
   repositorio junto con el ejecutable, o mediante una oferta escrita
   equivalente a la del Art. 6 de la GPL (válida por el plazo que exige la
   licencia). Redactar y publicar esa oferta es una decisión del
   responsable del producto, no una tarea mecánica de inventario — por eso
   no se redacta aquí un compromiso vinculante en nombre de la organización.

## E. ¿Permite el modelo de distribución frozen actual cumplir esto razonablemente?

Sí, técnicamente: el repositorio ya contiene todo lo necesario para (2), y
(1) es trivial. Lo que el modelo *no* resuelve por sí solo es *hacer llegar*
ese material a quien reciba una copia del ejecutable — eso requiere una
decisión explícita (acompañar el repo, o publicar una oferta escrita) que
excede el alcance mecánico de este bloque P1 (documentación + inventario,
sin tocar runtime).

## Clasificación (seguir la escala del bloque P1-LICENSES)

**B — Requiere material adicional antes de entregar copias.**

La documentación (aviso + texto LGPLv3 íntegro) queda completa con este
bloque P1 y es suficiente para build/pruebas internas. Antes de entregar
copias del `.exe` a destinatarios externos al equipo de desarrollo, alguien
con autoridad sobre la distribución debe decidir y ejecutar el mecanismo de
acceso al Corresponding Application Code (acompañar el repo, u ofrecerlo
por escrito) descrito en el punto D. "Beta interna" no exime de esto per se
(building/testing interno sí está cubierto; entregar copias a terceros no).
