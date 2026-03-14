"""Tests for CLI subcommands via subprocess and mocking."""
import json
import os
import subprocess
import sys
from unittest.mock import patch, MagicMock
import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts', 'deye_cli.py')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))


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


class TestStatus:
    @patch('deye_cli._http_post')
    @patch('deye_cli.get_session')
    def test_status_json_output(self, mock_session, mock_post):
        from deye_cli import cmd_status
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {
            "success": True,
            "deviceDataList": [{
                "deviceSn": "SN123",
                "dataList": [
                    {"key": "SOC", "value": "85", "unit": "%"},
                    {"key": "BatteryPower", "value": "500", "unit": "W"},
                    {"key": "TotalGridPower", "value": "-200", "unit": "W"},
                    {"key": "TotalDCInputPower", "value": "3000", "unit": "W"},
                    {"key": "TotalConsumptionPower", "value": "1500", "unit": "W"},
                ],
            }],
        }
        # Create a mock args object
        args = MagicMock()
        args.json = True
        args.device_sn = None
        args.env_path = "dummy"
        args.command = "status"

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cmd_status(args)
        output = json.loads(f.getvalue())
        assert output["success"] is True
        assert "SOC" in str(output["data"])


class TestDevices:
    @patch('deye_cli._http_post')
    @patch('deye_cli.get_session')
    def test_devices_json_output(self, mock_session, mock_post):
        from deye_cli import cmd_devices
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        # station/list response
        mock_post.side_effect = [
            {"success": True, "stationList": [{"id": 1, "name": "Home"}]},
            {"success": True, "deviceListItems": [
                {"deviceSn": "SN123", "deviceType": "INVERTER", "deviceStatus": 1},
            ]},
        ]
        args = MagicMock()
        args.json = True
        args.device_sn = None
        args.env_path = "dummy"
        args.command = "devices"

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cmd_devices(args)
        output = json.loads(f.getvalue())
        assert output["success"] is True


class TestHistory:
    @patch('deye_cli._http_post')
    @patch('deye_cli.get_session')
    def test_history_json_output(self, mock_session, mock_post):
        from deye_cli import cmd_history
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {
            "success": True,
            "dataList": [
                {"time": "1710300000", "itemList": [
                    {"key": "SOC", "value": "85", "unit": "%"},
                ]},
            ],
        }
        args = MagicMock()
        args.json = True
        args.device_sn = None
        args.env_path = "dummy"
        args.command = "history"
        args.granularity = 1
        args.start = "2026-03-13"
        args.end = "2026-03-13"
        args.points = None

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cmd_history(args)
        output = json.loads(f.getvalue())
        assert output["success"] is True
        assert len(output["data"]["records"]) == 1
