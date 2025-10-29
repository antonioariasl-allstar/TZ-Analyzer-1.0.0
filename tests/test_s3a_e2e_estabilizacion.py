#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_s3a_e2e_estabilizacion.py - SPRINT 3A.6 ESTABILIZACIÓN E2E
================================================================

✅ ESTADO: TESTING RIGUROSO POST-MODULARIZACIÓN
🎯 PROPÓSITO: Confirmar ZERO regressions tras extracción menú tz_cli
📍 CASOS: Normal, IMEI decimal fantasma, Sin ubicación

RESPONSABILIDADES:
- Testing E2E con 3 bitácoras diferentes
- Comparación outputs: checksums, size, contenido
- Verificación estructura archivos (HTML/KML/KMZ/hashes)
- Documentación matriz de casos y resultados

EJECUCIÓN:
python tests/test_s3a_e2e_estabilizacion.py

FECHA: 29 octubre 2025 - Sprint 3A.6
"""

import os
import sys
import hashlib
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any

# Añadir root al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from script_principal_bitacoras_refactory import bootstrap_config

class S3AEstabilizacionTester:
    """
    Tester E2E para validación post-extracción menú modular
    
    Ejecuta casos de test con diferentes bitácoras y compara
    outputs para detectar regressions tras Sprint 3A.
    """
    
    def __init__(self):
        self.test_cases = [
            {
                'name': 'bitacora_base_xlsx',
                'file': 'tests/data/bitacora_test.tsv.xlsx',
                'description': 'Bitácora base Excel - caso estándar existente'
            },
            {
                'name': 'caso_normal_tsv',
                'file': 'tests/data/bitacora_caso_normal.tsv',
                'description': 'Bitácora TSV normal con coordenadas válidas'
            },
            {
                'name': 'imei_decimal_fantasma', 
                'file': 'tests/data/bitacora_imei_decimal_fantasma.tsv',
                'description': 'IMEI con decimales .0, .00, notación científica'
            },
            {
                'name': 'sin_ubicacion',
                'file': 'tests/data/bitacora_sin_ubicacion.tsv', 
                'description': 'Coordenadas faltantes, NULL, N/A, vacías'
            }
        ]
        
        self.results = {}
        self.output_base = "outputs_s3a_e2e"
        self.test_start_time = datetime.now()
        
    def setup_test_environment(self):
        """Preparar entorno para testing E2E"""
        print("🔧 Configurando entorno de testing S3A.6...")
        
        # Bootstrap config como usuario normal
        bootstrap_config()
        
        # Crear directorio base outputs si no existe
        os.makedirs(self.output_base, exist_ok=True)
        
        # Verificar archivos de test existen
        for case in self.test_cases:
            if not os.path.exists(case['file']):
                raise FileNotFoundError(f"Archivo test faltante: {case['file']}")
                
        print(f"✅ Entorno listo - {len(self.test_cases)} casos configurados")
        
    def calculate_file_signature(self, filepath: str) -> Dict[str, Any]:
        """
        Calcular firma de archivo para comparaciones
        
        Retorna dict con checksum, tamaño, timestamps para
        detectar cambios en outputs generados.
        """
        if not os.path.exists(filepath):
            return {'exists': False}
            
        stat = os.stat(filepath)
        
        with open(filepath, 'rb') as f:
            content = f.read()
            
        return {
            'exists': True,
            'size': stat.st_size,
            'md5': hashlib.md5(content).hexdigest(),
            'sha256': hashlib.sha256(content).hexdigest()[:16],  # Primeros 16 chars
            'modified': stat.st_mtime
        }
        
    def run_single_case(self, test_case: Dict[str, str]) -> Dict[str, Any]:
        """
        Ejecutar un caso de test individual
        
        Simula entrada usuario para procesamiento automático
        y captura todos los outputs generados.
        """
        case_name = test_case['name']
        input_file = test_case['file']
        
        print(f"\n🧪 Ejecutando caso: {case_name}")
        print(f"   📄 Archivo: {input_file}")
        print(f"   📝 {test_case['description']}")
        
        # Preparar directorio específico para caso
        case_output_dir = os.path.join(self.output_base, case_name)
        os.makedirs(case_output_dir, exist_ok=True)
        
        # Simular inputs usuario para automatización
        test_inputs = [
            "1",  # Opción [1] Procesar archivo
            os.path.abspath(input_file),  # Path archivo
            "10",  # Top antenas
            "y",  # Confirmar procesamiento
            "3"   # Salir tras procesamiento
        ]
        
        # Ejecutar con inputs simulados
        start_time = time.time()
        
        try:
            # Import directo para testing (no subprocess para debugging)
            from script_principal_bitacoras_refactory import run_cli
            
            # TODO: Implementar input mocking para automatización
            # Por ahora ejecutamos test manual documentando proceso
            execution_time = time.time() - start_time
            
            # Catalogar outputs esperados
            expected_outputs = self._catalog_expected_outputs(case_output_dir)
            
            result = {
                'status': 'manual_required',
                'execution_time': execution_time,
                'inputs_simulated': test_inputs,
                'expected_outputs': expected_outputs,
                'message': 'Requiere ejecución manual - documentar en S3A_CLI_NOTES.md'
            }
            
        except Exception as e:
            result = {
                'status': 'error',
                'error': str(e),
                'execution_time': time.time() - start_time
            }
            
        return result
        
    def _catalog_expected_outputs(self, output_dir: str) -> List[str]:
        """Catalogar archivos de output esperados para caso"""
        # Patrones de archivos que debería generar el sistema
        expected_patterns = [
            "*.html",       # Reporte principal  
            "*.kml",        # Archivo KML
            "*.kmz",        # Archivo KMZ
            "*_hashes.txt", # Hash verificación
            "*_errores.txt" # Log errores si aplica
        ]
        
        return expected_patterns
        
    def compare_outputs(self, baseline_case: str, current_case: str) -> Dict[str, Any]:
        """
        Comparar outputs entre casos para detectar regressions
        
        Compara estructura, checksums y contenido con tolerancia
        para timestamps y IDs dinámicos.
        """
        baseline_dir = os.path.join(self.output_base, baseline_case)
        current_dir = os.path.join(self.output_base, current_case)
        
        comparison = {
            'baseline': baseline_case,
            'current': current_case,
            'files_compared': [],
            'differences': [],
            'identical_files': [],
            'missing_files': []
        }
        
        # TODO: Implementar comparación real tras ejecución manual
        comparison['status'] = 'pending_manual_execution'
        
        return comparison
        
    def generate_test_report(self) -> str:
        """
        Generar reporte completo de testing S3A.6
        
        Incluye matriz de casos, resultados, comparaciones
        y recomendaciones para tag v1.0.1-rc1.
        """
        report_path = os.path.join(self.output_base, "S3A_E2E_REPORT.md")
        
        report_content = f"""# SPRINT 3A.6 - REPORTE ESTABILIZACIÓN E2E

**FECHA**: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}  
**OBJETIVO**: Validación post-extracción menú modular  
**ESTADO**: Testing riguroso para confirmación zero regressions  

## 🎯 MATRIZ DE CASOS DE TEST

| Caso | Archivo | Descripción | Status |
|------|---------|-------------|--------|
"""
        
        for case in self.test_cases:
            case_name = case['name']
            result = self.results.get(case_name, {'status': 'pending'})
            status_emoji = '⏳' if result['status'] == 'pending' else '✅' if result['status'] == 'success' else '❌'
            
            report_content += f"| {case_name} | {case['file']} | {case['description']} | {status_emoji} {result['status']} |\n"
            
        report_content += f"""

## 📊 RESULTADOS DETALLADOS

### Caso 1: Normal
- **Propósito**: Baseline con datos válidos estándar
- **Esperado**: KML/KMZ/HTML sin errores, 10 antenas top
- **Validaciones**: Checksums, estructura archivos, contenido

### Caso 2: IMEI Decimal Fantasma  
- **Propósito**: Handling decimales .0, notación científica
- **Esperado**: Normalización correcta IMEI, sin errores parsing
- **Validaciones**: IMEI processing consistente, outputs válidos

### Caso 3: Sin Ubicación
- **Propósito**: Manejo coordenadas faltantes/NULL/N/A
- **Esperado**: Graceful handling, reportes de errores claros
- **Validaciones**: No crashes, error reporting apropiado

## 🔍 COMPARACIÓN DE OUTPUTS

### Estructura Archivos Esperada:
```
outputs_s3a_e2e/
├── caso_normal/
│   ├── TZ_Analysis_Report_YYYYMMDD_HHMMSS.html
│   ├── mapa_calor_antenas_YYYYMMDD_HHMMSS.kml  
│   ├── datos_completos_YYYYMMDD_HHMMSS.kmz
│   ├── verificacion_hashes_YYYYMMDD_HHMMSS.txt
│   └── errores_procesamiento_YYYYMMDD_HHMMSS.txt (si aplica)
├── imei_decimal_fantasma/ (misma estructura)
└── sin_ubicacion/ (misma estructura)
```

### Tolerancias Comparación:
- ✅ **Timestamps**: Ignorar diferencias en nombres archivos
- ✅ **IDs Dinámicos**: Normalizar IDs secuenciales  
- ✅ **Checksums**: Comparar contenido estructural
- ❌ **Estructura**: Mismos archivos generados
- ❌ **Datos Core**: Coordenadas, antenas idénticas

## 🚀 RECOMENDACIÓN TAGGING

### Para v1.0.1-rc1:
- ✅ **SI**: Todos casos pasan sin regressions
- ✅ **SI**: Outputs estructuralmente idénticos
- ✅ **SI**: Zero diferencias contenido core
- ❌ **NO**: Cualquier regression detectada

### Criterios Release:
1. Menú modular funciona idénticamente
2. Generación KML/KMZ sin cambios
3. Reportes HTML estructuralmente iguales  
4. Manejo errores consistente
5. Performance sin degradación significativa

---

**NOTA**: Este reporte requiere ejecución manual de casos para completar validaciones.
Documentar resultados reales en esta sección tras testing.
"""

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
            
        return report_path
        
    def run_all_tests(self):
        """Ejecutar suite completa de tests S3A.6"""
        print("🚀 INICIANDO SPRINT 3A.6 - ESTABILIZACIÓN E2E")
        print("=" * 60)
        
        self.setup_test_environment()
        
        # Ejecutar cada caso
        for test_case in self.test_cases:
            try:
                result = self.run_single_case(test_case)
                self.results[test_case['name']] = result
            except Exception as e:
                print(f"❌ Error en caso {test_case['name']}: {e}")
                self.results[test_case['name']] = {
                    'status': 'error',
                    'error': str(e)
                }
                
        # Generar reporte
        report_path = self.generate_test_report()
        
        print(f"\n📋 Reporte generado: {report_path}")
        print("\n🎯 PRÓXIMOS PASOS:")
        print("1. Ejecutar manualmente cada caso documentando outputs")  
        print("2. Comparar checksums/contenido vs baseline")
        print("3. Documentar en docs/S3A_CLI_NOTES.md")
        print("4. Tag v1.0.1-rc1 si todo OK")
        print("5. Proceder con Sprint 3B (CLI Click)")


if __name__ == "__main__":
    tester = S3AEstabilizacionTester()
    tester.run_all_tests()