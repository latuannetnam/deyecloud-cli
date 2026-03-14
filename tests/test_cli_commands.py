"""Tests for CLI subcommands via subprocess."""
import json
import os
import subprocess
import sys
import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts', 'deye_cli.py')


class TestSetup:
    def test_creates_env_template(self, tmp_path):
        env_path = str(tmp_path / ".env")
        result = subprocess.run(
            [sys.executable, SCRIPT, "--json", "--env-path", env_path, "setup"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert os.path.exists(env_path)
