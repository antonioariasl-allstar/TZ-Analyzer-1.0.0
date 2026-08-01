"""
Tests para tz_core.time_utils

Valida el correcto funcionamiento de utilities temporales.
"""

import pytest
import pandas as pd
from datetime import time as _time

from tz_core.time_utils import (
    hhmmss_to_time_or_none, en_rango_tiempo, en_rango_minutos, 
    clasificar_rango_sv, RANGOS_SV, normalize_hour_to_hhmmss,
    to_datetime_series,
)


class TestHhmmssToTimeOrNone:
    """Tests para la función hhmmss_to_time_or_none."""
    
    def test_conversiones_exitosas(self):
        """Debe convertir exitosamente strings HH:MM:SS válidos."""
        assert hhmmss_to_time_or_none("14:30:15") == _time(14, 30, 15)
        assert hhmmss_to_time_or_none("00:00:00") == _time(0, 0, 0)
        assert hhmmss_to_time_or_none("23:59:59") == _time(23, 59, 59)
        assert hhmmss_to_time_or_none("06:45:30") == _time(6, 45, 30)
    
    def test_formato_con_limitacion_caracteres(self):
        """Debe tomar máximo 8 caracteres del string."""
        assert hhmmss_to_time_or_none("14:30:15extrajunk") == _time(14, 30, 15)
        assert hhmmss_to_time_or_none("06:45:30.123") == _time(6, 45, 30)
    
    def test_conversiones_fallidas(self):
        """Debe retornar None para strings inválidos."""
        assert hhmmss_to_time_or_none("invalid") is None
        assert hhmmss_to_time_or_none("25:00:00") is None  # hora inválida
        assert hhmmss_to_time_or_none("14:60:00") is None  # minuto inválido
        assert hhmmss_to_time_or_none("14:30:60") is None  # segundo inválido
        assert hhmmss_to_time_or_none("") is None
        assert hhmmss_to_time_or_none(None) is None
    
    def test_formatos_edge_cases(self):
        """Debe manejar casos especiales y edge cases."""
        assert hhmmss_to_time_or_none("1:2:3") == _time(1, 2, 3)
        assert hhmmss_to_time_or_none("  14:30:15  ") == _time(14, 30, 15)
        assert hhmmss_to_time_or_none("14:30") is None  # formato incompleto


class TestNormalizeHourToHhmmss:
    """Tests para normalize_hour_to_hhmmss."""

    def test_separadores_varios(self):
        assert normalize_hour_to_hhmmss("6.30") == "06:30:00"
        assert normalize_hour_to_hhmmss("14-20") == "14:20:00"
        assert normalize_hour_to_hhmmss("18/45") == "18:45:00"

    def test_timestamps_y_parciales(self):
        assert normalize_hour_to_hhmmss("2025-01-04 21:15:30") == "21:15:30"
        assert normalize_hour_to_hhmmss("09:15") == "09:15:00"

    def test_invalidos(self):
        assert normalize_hour_to_hhmmss("invalid") is None
        assert normalize_hour_to_hhmmss(None) is None


class TestEnRangoTiempo:
    """Tests para la función en_rango_tiempo."""
    
    def test_rango_normal_dentro_mismo_dia(self):
        """Debe funcionar para rangos normales dentro del mismo día."""
        # 14:30 está entre 12:00 y 18:00
        assert en_rango_tiempo(_time(14, 30), _time(12, 0), _time(18, 0)) == True
        # 10:00 NO está entre 12:00 y 18:00
        assert en_rango_tiempo(_time(10, 0), _time(12, 0), _time(18, 0)) == False
        # 20:00 NO está entre 12:00 y 18:00
        assert en_rango_tiempo(_time(20, 0), _time(12, 0), _time(18, 0)) == False
    
    def test_rango_en_limites(self):
        """Debe incluir los límites del rango."""
        # Exactamente en el inicio
        assert en_rango_tiempo(_time(12, 0), _time(12, 0), _time(18, 0)) == True
        # Exactamente en el final
        assert en_rango_tiempo(_time(18, 0), _time(12, 0), _time(18, 0)) == True
    
    def test_rango_cruza_medianoche(self):
        """Debe manejar rangos que cruzan medianoche."""
        # Rango 22:00 a 06:00 (cruza medianoche)
        ini = _time(22, 0)
        fin = _time(6, 0)
        
        # Dentro del rango nocturno
        assert en_rango_tiempo(_time(23, 30), ini, fin) == True
        assert en_rango_tiempo(_time(1, 0), ini, fin) == True
        assert en_rango_tiempo(_time(5, 30), ini, fin) == True
        
        # Fuera del rango nocturno
        assert en_rango_tiempo(_time(12, 0), ini, fin) == False
        assert en_rango_tiempo(_time(18, 0), ini, fin) == False
    
    def test_rango_cruza_medianoche_limites(self):
        """Debe manejar límites en rangos que cruzan medianoche."""
        ini = _time(22, 0)
        fin = _time(6, 0)
        
        # Exactamente en los límites
        assert en_rango_tiempo(_time(22, 0), ini, fin) == True
        assert en_rango_tiempo(_time(6, 0), ini, fin) == True


class TestEnRangoMinutos:
    """Tests para la función en_rango_minutos."""
    
    def test_rango_normal_minutos(self):
        """Debe funcionar para rangos normales en minutos."""
        # 14:30 (870 min) está entre 12:00 (720 min) y 18:00 (1080 min)
        assert en_rango_minutos(870, 720, 1080) == True
        # 10:00 (600 min) NO está entre 12:00 y 18:00
        assert en_rango_minutos(600, 720, 1080) == False
    
    def test_rango_cruza_medianoche_minutos(self):
        """Debe manejar rangos que cruzan medianoche en minutos."""
        # Rango 22:00 (1320 min) a 06:00 (360 min)
        ini = 1320  # 22:00
        fin = 360   # 06:00
        
        # Dentro del rango nocturno
        assert en_rango_minutos(1410, ini, fin) == True  # 23:30
        assert en_rango_minutos(60, ini, fin) == True    # 01:00
        assert en_rango_minutos(330, ini, fin) == True   # 05:30
        
        # Fuera del rango nocturno
        assert en_rango_minutos(720, ini, fin) == False  # 12:00
        assert en_rango_minutos(1080, ini, fin) == False # 18:00
    
    def test_limites_minutos(self):
        """Debe incluir los límites del rango en minutos."""
        assert en_rango_minutos(720, 720, 1080) == True   # límite inicio
        assert en_rango_minutos(1080, 720, 1080) == True  # límite fin


class TestClasificarRangoSv:
    """Tests para la función clasificar_rango_sv."""
    
    def test_clasificacion_madrugada(self):
        """Debe clasificar correctamente horarios de madrugada."""
        assert clasificar_rango_sv("00:00:00") == "madrugada"
        assert clasificar_rango_sv("03:30:00") == "madrugada"
        assert clasificar_rango_sv("05:59:59") == "madrugada"
    
    def test_clasificacion_manana(self):
        """Debe clasificar correctamente horarios de mañana."""
        assert clasificar_rango_sv("06:00:00") == "manana"
        assert clasificar_rango_sv("09:30:00") == "manana"
        assert clasificar_rango_sv("11:59:59") == "manana"
    
    def test_clasificacion_tarde(self):
        """Debe clasificar correctamente horarios de tarde."""
        assert clasificar_rango_sv("12:00:00") == "tarde"
        assert clasificar_rango_sv("15:30:00") == "tarde"
        assert clasificar_rango_sv("17:59:59") == "tarde"
    
    def test_clasificacion_noche(self):
        """Debe clasificar correctamente horarios de noche."""
        assert clasificar_rango_sv("18:00:00") == "noche"
        assert clasificar_rango_sv("21:30:00") == "noche"
        assert clasificar_rango_sv("23:59:00") == "noche"
    
    def test_horarios_invalidos(self):
        """Debe retornar None para horarios inválidos."""
        assert clasificar_rango_sv("invalid") is None
        assert clasificar_rango_sv("25:00:00") is None
        assert clasificar_rango_sv("") is None
        # assert clasificar_rango_sv(None) is None  # Skip None test due to typing
    
    def test_constantes_rangos_sv(self):
        """Debe tener definidas las constantes RANGOS_SV correctamente."""
        assert "madrugada" in RANGOS_SV
        assert "manana" in RANGOS_SV
        assert "tarde" in RANGOS_SV
        assert "noche" in RANGOS_SV
        
        # Verificar estructura de cada rango
        for clave, (nombre, ini, fin) in RANGOS_SV.items():
            assert isinstance(nombre, str)
            assert isinstance(ini, _time)
            assert isinstance(fin, _time)


class TestCompatibilidad:
    """Tests de compatibilidad con aliases."""
    
    def test_aliases_existen(self):
        """Los aliases deben existir para compatibilidad."""
        from tz_core.time_utils import (
            _hhmmss_to_time_or_none, _en_rango, 
            _en_rango_minutos, _clasificar_rango_sv
        )
        
        # Deben ser la misma función
        assert _hhmmss_to_time_or_none is hhmmss_to_time_or_none
        assert _en_rango is en_rango_tiempo
        assert _en_rango_minutos is en_rango_minutos
        assert _clasificar_rango_sv is clasificar_rango_sv
    
    def test_aliases_funcionan(self):
        """Los aliases deben funcionar igual que las funciones principales."""
        from tz_core.time_utils import (
            _hhmmss_to_time_or_none, _en_rango, _clasificar_rango_sv
        )
        
        assert _hhmmss_to_time_or_none("14:30:15") == hhmmss_to_time_or_none("14:30:15")
        assert _en_rango(_time(14, 30), _time(12, 0), _time(18, 0)) == en_rango_tiempo(_time(14, 30), _time(12, 0), _time(18, 0))
        assert _clasificar_rango_sv("14:30:00") == clasificar_rango_sv("14:30:00")


class TestToDatetimeSeries:
    """Regresiones para fechas ISO usadas por el selector diario del HTML."""

    def test_prefiere_datetime_evento_sin_invertir_fecha_iso(self):
        """El timestamp canónico tiene precedencia sobre representaciones derivadas."""
        df = pd.DataFrame({
            "fecha": ["2026-05-01 00:00:00", "2026-07-28 00:00:00"],
            "hora": ["09:00:14", "17:16:31"],
            "datetime_evento": pd.to_datetime([
                "2026-05-01 09:00:14",
                "2026-07-28 17:16:31",
            ]),
        })

        result = to_datetime_series(df)

        assert result.tolist() == [
            pd.Timestamp("2026-05-01 09:00:14"),
            pd.Timestamp("2026-07-28 17:16:31"),
        ]

    def test_combina_fecha_iso_y_hora_sin_datetime_evento(self):
        """El fallback fecha+hora conserva YYYY-MM-DD y agrega la hora."""
        df = pd.DataFrame({
            "fecha": ["2026-05-01 00:00:00", "2026-07-28 00:00:00"],
            "hora": ["09:00:14", "17:16:31"],
        })

        result = to_datetime_series(df)

        assert result.tolist() == [
            pd.Timestamp("2026-05-01 09:00:14"),
            pd.Timestamp("2026-07-28 17:16:31"),
        ]
