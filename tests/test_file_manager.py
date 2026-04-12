"""
test_file_manager.py
Pruebas unitarias del módulo utils/file_manager.py.
"""

import os
import shutil
import tempfile

import pytest

from utils.file_manager import (
    temp_path,
    read_bytes,
    file_size_mb,
    file_exists,
    _cleanup,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_session_state(monkeypatch):
    """Simula st.session_state como un dict simple."""
    state = {}
    import utils.file_manager as fm
    monkeypatch.setattr(fm.st, "session_state", state, raising=False)
    return state


@pytest.fixture
def temp_session_dir(mock_session_state):
    """Crea un directorio temporal limpio y lo registra en session_state."""
    d = tempfile.mkdtemp(prefix="cottas_fm_test_")
    mock_session_state["temp_dir"] = d
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ─── Tests de temp_path ───────────────────────────────────────────────────────

class TestTempPath:
    def test_returns_path_inside_session_dir(self, temp_session_dir):
        p = temp_path("foo.cottas")
        assert p.startswith(temp_session_dir)
        assert p.endswith("foo.cottas")

    def test_different_filenames_give_different_paths(self, temp_session_dir):
        p1 = temp_path("a.cottas")
        p2 = temp_path("b.cottas")
        assert p1 != p2

    def test_path_not_created_automatically(self, temp_session_dir):
        p = temp_path("nonexistent.cottas")
        assert not os.path.exists(p)


# ─── Tests de read_bytes ──────────────────────────────────────────────────────

class TestReadBytes:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02\x03")
        assert read_bytes(str(f)) == b"\x00\x01\x02\x03"

    def test_reads_text_file_as_bytes(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("hello", encoding="utf-8")
        assert read_bytes(str(f)) == b"hello"

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_bytes(str(tmp_path / "missing.bin"))

    def test_empty_file_returns_empty_bytes(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert read_bytes(str(f)) == b""


# ─── Tests de file_size_mb ────────────────────────────────────────────────────

class TestFileSizeMb:
    def test_known_size(self, tmp_path):
        f = tmp_path / "sized.bin"
        f.write_bytes(b"A" * (1024 * 1024))   # exactamente 1 MB
        assert abs(file_size_mb(str(f)) - 1.0) < 1e-6

    def test_empty_file_is_zero(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert file_size_mb(str(f)) == 0.0

    def test_small_file_less_than_one_mb(self, tmp_path):
        f = tmp_path / "small.bin"
        f.write_bytes(b"x" * 512)
        assert file_size_mb(str(f)) < 1.0


# ─── Tests de file_exists ────────────────────────────────────────────────────

class TestFileExists:
    def test_existing_file_returns_true(self, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("hi")
        assert file_exists(str(f)) is True

    def test_missing_file_returns_false(self, tmp_path):
        assert file_exists(str(tmp_path / "nope.txt")) is False

    def test_directory_returns_false(self, tmp_path):
        # file_exists debe devolver False para directorios
        assert file_exists(str(tmp_path)) is False


# ─── Tests de _cleanup ───────────────────────────────────────────────────────

class TestCleanup:
    def test_removes_existing_directory(self, tmp_path):
        d = str(tmp_path / "to_remove")
        os.makedirs(d)
        assert os.path.isdir(d)
        _cleanup(d)
        assert not os.path.exists(d)

    def test_missing_directory_does_not_raise(self):
        _cleanup("/tmp/cottas_nonexistent_xyz_12345")

    def test_removes_directory_with_contents(self, tmp_path):
        d = tmp_path / "nested"
        (d / "sub").mkdir(parents=True)
        (d / "sub" / "file.txt").write_text("data")
        _cleanup(str(d))
        assert not d.exists()
