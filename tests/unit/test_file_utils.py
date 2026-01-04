"""
Tests para tz_core.file_utils - Utilidades de operaciones de archivos.

Cobertura:
- Escritura de archivos hash con casos normales y de error
- Copia de archivos con validación de rutas y manejo de errores
- Casos edge: archivos inexistentes, permisos, directorios
- Compatibilidad con aliases de funciones
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from tz_io.file_io import (
    escribe_hashes_txt, 
    copiar_logo_a_salida,
    _escribe_hashes_txt,  # alias
    _copiar_logo_a_salida  # alias
)
from tz_core.file_utils import relocate_kmz_file


class TestEscribeHashesTxt:
    """Tests para escritura de archivos hash"""
    
    def test_escribe_hashes_basico(self, tmp_path):
        """Debe escribir archivo hash correctamente con pares válidos"""
        # Crear archivos temporales para testing
        file1 = tmp_path / "test1.txt"
        file2 = tmp_path / "test2.txt"
        file1.write_text("contenido 1", encoding="utf-8")
        file2.write_text("contenido 2", encoding="utf-8")
        
        # Pares para procesar
        pares = [
            (str(file1), "test1.txt"),
            (str(file2), "subdir/test2.txt")
        ]
        
        # Escribir hashes
        hash_file = tmp_path / "hashes.txt"
        escribe_hashes_txt(str(hash_file), pares)
        
        # Verificar contenido
        content = hash_file.read_text(encoding="utf-8")
        lines = content.strip().split('\n')
        
        assert len(lines) == 2
        assert lines[0].startswith("SHA256  ")
        assert lines[0].endswith("  test1.txt")
        assert lines[1].startswith("SHA256  ")
        assert lines[1].endswith("  subdir/test2.txt")
        
        # Verificar formato hexadecimal
        hash1 = lines[0].split("  ")[1]
        hash2 = lines[1].split("  ")[1]
        assert len(hash1) == 64  # SHA256 = 64 chars hex
        assert len(hash2) == 64
        assert all(c in '0123456789abcdef' for c in hash1.lower())
        assert all(c in '0123456789abcdef' for c in hash2.lower())
    
    def test_escribe_hashes_archivo_inexistente(self, tmp_path):
        """Debe manejar archivos inexistentes con mensaje de error"""
        pares = [
            ("archivo_que_no_existe.txt", "missing.txt"),
            ("/ruta/inexistente/archivo.txt", "otro_missing.txt")
        ]
        
        hash_file = tmp_path / "hashes_error.txt"
        escribe_hashes_txt(str(hash_file), pares)
        
        content = hash_file.read_text(encoding="utf-8")
        lines = content.strip().split('\n')
        
        assert len(lines) == 2
        assert lines[0].startswith("# ERROR hashing missing.txt:")
        assert lines[1].startswith("# ERROR hashing otro_missing.txt:")
    
    def test_escribe_hashes_mixto(self, tmp_path):
        """Debe manejar mezcla de archivos válidos e inválidos"""
        # Crear un archivo válido
        valid_file = tmp_path / "valid.txt"
        valid_file.write_text("test content", encoding="utf-8")
        
        pares = [
            (str(valid_file), "valid.txt"),
            ("inexistente.txt", "missing.txt"),
        ]
        
        hash_file = tmp_path / "hashes_mixto.txt"
        escribe_hashes_txt(str(hash_file), pares)
        
        content = hash_file.read_text(encoding="utf-8")
        lines = content.strip().split('\n')
        
        assert len(lines) == 2
        assert lines[0].startswith("SHA256  ")
        assert lines[0].endswith("  valid.txt")
        assert lines[1].startswith("# ERROR hashing missing.txt:")
    
    def test_escribe_hashes_pares_vacios(self, tmp_path):
        """Debe manejar lista vacía de pares"""
        hash_file = tmp_path / "hashes_vacio.txt"
        escribe_hashes_txt(str(hash_file), [])
        
        content = hash_file.read_text(encoding="utf-8")
        assert content == "\n"  # Solo newline final
    
    def test_escribe_hashes_encoding_utf8(self, tmp_path):
        """Debe manejar nombres de archivo con caracteres Unicode"""
        # Crear archivo con nombre Unicode
        unicode_file = tmp_path / "archivo_café_ñandú.txt"
        unicode_file.write_text("contenido unicode", encoding="utf-8")
        
        pares = [(str(unicode_file), "café_ñandú.txt")]
        
        hash_file = tmp_path / "hashes_unicode.txt"
        escribe_hashes_txt(str(hash_file), pares)
        
        content = hash_file.read_text(encoding="utf-8")
        assert "café_ñandú.txt" in content
        assert content.startswith("SHA256  ")


class TestCopiarLogoASalida:
    """Tests para copia de archivos logo"""
    
    def test_copiar_logo_basico(self, tmp_path):
        """Debe copiar archivo logo correctamente"""
        # Crear archivo logo fuente
        logo_src = tmp_path / "logo_source.png"
        logo_src.write_bytes(b"PNG fake content")
        
        # Crear directorio destino
        dest_dir = tmp_path / "output"
        
        # Copiar logo
        result = copiar_logo_a_salida(str(logo_src), str(dest_dir))
        
        # Verificar resultado
        assert result == "logo_source.png"
        
        # Verificar que el archivo fue copiado
        dest_file = dest_dir / "logo_source.png"
        assert dest_file.exists()
        assert dest_file.read_bytes() == b"PNG fake content"
    
    def test_copiar_logo_crea_directorio(self, tmp_path):
        """Debe crear directorio destino si no existe"""
        logo_src = tmp_path / "logo.png"
        logo_src.write_bytes(b"logo data")
        
        # Directorio que no existe
        dest_dir = tmp_path / "non_existent" / "subdir"
        
        result = copiar_logo_a_salida(str(logo_src), str(dest_dir))
        
        assert result == "logo.png"
        assert (dest_dir / "logo.png").exists()
    
    def test_copiar_logo_archivo_inexistente(self, tmp_path):
        """Debe retornar None para archivo inexistente"""
        dest_dir = tmp_path / "output"
        
        result = copiar_logo_a_salida("archivo_que_no_existe.png", str(dest_dir))
        
        assert result is None
    
    def test_copiar_logo_ruta_vacia(self, tmp_path):
        """Debe retornar None para ruta vacía"""
        dest_dir = tmp_path / "output"
        
        result = copiar_logo_a_salida("", str(dest_dir))
        assert result is None
    
    def test_copiar_logo_mismo_archivo(self, tmp_path):
        """Debe evitar copiar archivo sobre sí mismo"""
        # Crear archivo en el directorio destino
        dest_dir = tmp_path / "output"
        dest_dir.mkdir()
        logo_file = dest_dir / "logo.png"
        logo_file.write_bytes(b"original content")
        
        # Intentar copiarlo sobre sí mismo
        result = copiar_logo_a_salida(str(logo_file), str(dest_dir))
        
        assert result == "logo.png"
        # Archivo debe seguir existiendo con contenido original
        assert logo_file.read_bytes() == b"original content"
    
    def test_copiar_logo_ruta_relativa_fallback(self, tmp_path):
        """Debe buscar archivo en directorio base si ruta relativa no existe"""
        # Esta función busca en el directorio del proyecto
        # Creamos un mock para simular el comportamiento
        dest_dir = tmp_path / "output"
        
        with patch('tz_core.file_utils.os.path.exists') as mock_exists:
            # Primera llamada (ruta absoluta) retorna False
            # Segunda llamada (fallback) retorna False también
            mock_exists.side_effect = [False, False]
            
            result = copiar_logo_a_salida("relative_logo.png", str(dest_dir))
            
            assert result is None
    
    def test_copiar_logo_preserva_extension(self, tmp_path):
        """Debe preservar extensión del archivo"""
        extensiones = [".png", ".jpg", ".svg", ".gif"]
        
        for ext in extensiones:
            logo_src = tmp_path / f"logo{ext}"
            logo_src.write_bytes(b"fake image")
            
            dest_dir = tmp_path / f"output{ext}"
            
            result = copiar_logo_a_salida(str(logo_src), str(dest_dir))
            
            assert result == f"logo{ext}"
            assert (dest_dir / f"logo{ext}").exists()
    
    @patch('tz_core.file_utils.shutil.copy2')
    def test_copiar_logo_error_copia(self, mock_copy, tmp_path):
        """Debe manejar errores durante la copia"""
        logo_src = tmp_path / "logo.png"
        logo_src.write_bytes(b"content")
        dest_dir = tmp_path / "output"
        
        # Simular error en copy2
        mock_copy.side_effect = Exception("Permission denied")
        
        result = copiar_logo_a_salida(str(logo_src), str(dest_dir))
        
        assert result is None


class TestRelocateKmzFile:
    """Tests para la relocalización de archivos KMZ."""

    def test_relocate_kmz_moves_file(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        kmz_name = "caso_demo_mapeo.kmz"
        src_file = source_dir / kmz_name
        src_file.write_bytes(b"kmz content")

        messages = []

        result = relocate_kmz_file(
            case_name="caso_demo",
            source_folder=str(source_dir),
            target_folder=str(target_dir),
            logger=messages.append,
        )

        assert result == str(target_dir / kmz_name)
        assert not src_file.exists()
        assert (target_dir / kmz_name).read_bytes() == b"kmz content"
        assert messages, "Debe registrar mensaje de depuración"

    def test_relocate_kmz_overwrites_existing(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        kmz_name = "caso_demo_mapeo.kmz"
        src_file = source_dir / kmz_name
        src_file.write_bytes(b"nuevo contenido")

        target_file = target_dir / kmz_name
        target_file.write_bytes(b"viejo contenido")

        result = relocate_kmz_file(
            case_name="caso_demo",
            source_folder=str(source_dir),
            target_folder=str(target_dir),
        )

        assert result == str(target_file)
        assert not src_file.exists()
        assert target_file.read_bytes() == b"nuevo contenido"

    def test_relocate_kmz_missing_source(self, tmp_path):
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        result = relocate_kmz_file(
            case_name="caso_demo",
            source_folder=str(tmp_path / "source"),
            target_folder=str(target_dir),
        )

        assert result is None
        assert not any(target_dir.iterdir())


class TestCompatibilidadAliases:
    """Tests para aliases de compatibilidad"""
    
    def test_alias_escribe_hashes_txt(self, tmp_path):
        """El alias _escribe_hashes_txt debe funcionar igual"""
        file1 = tmp_path / "test.txt"
        file1.write_text("test", encoding="utf-8")
        
        pares = [(str(file1), "test.txt")]
        hash_file = tmp_path / "hashes.txt"
        
        # Usar alias
        _escribe_hashes_txt(str(hash_file), pares)
        
        # Verificar resultado
        content = hash_file.read_text(encoding="utf-8")
        assert "SHA256  " in content
        assert "test.txt" in content
    
    def test_alias_copiar_logo_a_salida(self, tmp_path):
        """El alias _copiar_logo_a_salida debe funcionar igual"""
        logo_src = tmp_path / "logo.png"
        logo_src.write_bytes(b"logo")
        dest_dir = tmp_path / "output"
        
        # Usar alias
        result = _copiar_logo_a_salida(str(logo_src), str(dest_dir))
        
        assert result == "logo.png"
        assert (dest_dir / "logo.png").exists()


class TestCasosEdge:
    """Tests para casos edge y manejo de errores"""
    
    def test_escribe_hashes_directorio_readonly(self, tmp_path):
        """Debe manejar errores de permisos de escritura"""
        if os.name == 'nt':  # Windows
            pytest.skip("Test de permisos específico para Unix")
        
        # Crear directorio de solo lectura
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir(mode=0o444)
        
        hash_file = readonly_dir / "hashes.txt"
        
        with pytest.raises(PermissionError):
            escribe_hashes_txt(str(hash_file), [])
    
    def test_copiar_logo_caracteres_especiales(self, tmp_path):
        """Debe manejar nombres con caracteres especiales"""
        logo_src = tmp_path / "logo with spaces & símbolos.png"
        logo_src.write_bytes(b"content")
        
        dest_dir = tmp_path / "output"
        
        result = copiar_logo_a_salida(str(logo_src), str(dest_dir))
        
        assert result == "logo with spaces & símbolos.png"
        assert (dest_dir / "logo with spaces & símbolos.png").exists()