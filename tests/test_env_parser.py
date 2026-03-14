"""Tests for .env file parser — _load_env() and _save_env()."""
import os
import tempfile
import pytest

# We import from deye_cli via path manipulation
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))
from deye_cli import _load_env, _save_env


class TestLoadEnv:
    def test_basic_key_value(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("KEY1=value1\nKEY2=value2\n")
        result = _load_env(str(f))
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_skip_comments_and_blanks(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# comment\n\nKEY=val\n")
        result = _load_env(str(f))
        assert result == {"KEY": "val"}

    def test_strip_quotes(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("KEY='quoted_value'\nKEY2=\"double\"\n")
        result = _load_env(str(f))
        assert result["KEY"] == "quoted_value"
        assert result["KEY2"] == "double"

    def test_value_with_equals(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("TOKEN=abc=def=ghi\n")
        result = _load_env(str(f))
        assert result["TOKEN"] == "abc=def=ghi"

    def test_missing_file_returns_empty(self, tmp_path):
        result = _load_env(str(tmp_path / "nope"))
        assert result == {}

    def test_special_chars_in_value(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("PASS=!KY'[8iP7>XEm;\n")
        result = _load_env(str(f))
        assert result["PASS"] == "!KY'[8iP7>XEm;"


class TestSaveEnv:
    def test_update_existing_key(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("KEY1=old\nKEY2=keep\n")
        _save_env(str(f), {"KEY1": "new"})
        result = _load_env(str(f))
        assert result["KEY1"] == "new"
        assert result["KEY2"] == "keep"

    def test_add_new_key(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("KEY1=val1\n")
        _save_env(str(f), {"KEY2": "val2"})
        result = _load_env(str(f))
        assert result["KEY1"] == "val1"
        assert result["KEY2"] == "val2"

    def test_preserves_comments(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# comment\nKEY=val\n")
        _save_env(str(f), {"KEY": "new"})
        content = f.read_text()
        assert "# comment" in content

    def test_create_file_if_missing(self, tmp_path):
        f = tmp_path / "new.env"
        _save_env(str(f), {"KEY": "val"})
        result = _load_env(str(f))
        assert result["KEY"] == "val"
