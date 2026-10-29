"""Testes para o módulo de diagnósticos do sistema."""
from src.utils.diagnostics import find_ffmpeg, check_write_permission, run_startup_diagnostics
import tempfile
import os

def test_find_ffmpeg():
    # Na máquina do usuário sabemos que ffmpeg está instalado
    ok, path, ver = find_ffmpeg()
    assert ok is True
    assert path is not None

def test_check_write_permission():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert check_write_permission(tmpdir) is True

def test_run_startup_diagnostics():
    with tempfile.TemporaryDirectory() as tmpdir:
        res = run_startup_diagnostics(download_dir=tmpdir)
        assert res.ffmpeg_available is True
        assert res.write_permission is True
