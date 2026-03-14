"""Tests for deye_core — shared business logic."""
import hashlib
import json
import os
import sys
import time
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))


class TestCoreEnvParser:
    """Verify _load_env and _save_env are available from deye_core."""

    def test_load_env_basic(self, tmp_path):
        from deye_core import load_env
        f = tmp_path / ".env"
        f.write_text("KEY1=value1\nKEY2=value2\n")
        result = load_env(str(f))
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_save_env_update(self, tmp_path):
        from deye_core import load_env, save_env
        f = tmp_path / ".env"
        f.write_text("KEY1=old\nKEY2=keep\n")
        save_env(str(f), {"KEY1": "new"})
        result = load_env(str(f))
        assert result["KEY1"] == "new"
        assert result["KEY2"] == "keep"


class TestCoreHttpClient:
    """Verify HTTP functions are available from deye_core."""

    @patch('deye_core.urlopen')
    def test_http_post(self, mock_urlopen):
        from deye_core import http_post
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"success": True}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        result = http_post("http://example.com/api", {"key": "val"}, {})
        assert result == {"success": True}


class TestCoreAuth:
    """Verify auth functions are available from deye_core."""

    def test_hash_password(self):
        from deye_core import hash_password
        result = hash_password("test123")
        assert result == hashlib.sha256(b"test123").hexdigest()

    def test_get_session_cached(self, tmp_path):
        from deye_core import get_session
        env = tmp_path / ".env"
        future = str(int(time.time()) + 7200)
        env.write_text(
            "DEYE_BASE_URL=http://base\n"
            "DEYE_APP_ID=aid\nDEYE_APP_SECRET=sec\n"
            "DEYE_EMAIL=e@m\nDEYE_PASSWORD=pw\n"
            "DEYE_COMPANY_ID=0\n"
            f"DEYE_TOKEN=cached_tok\nDEYE_TOKEN_EXPIRES_AT={future}\n"
            "DEYE_DEVICE_SN=12345\n"
        )
        base, headers, sn = get_session(env_path=str(env))
        assert headers["Authorization"] == "bearer cached_tok"
        assert sn == "12345"


class TestCoreMethods:
    """Verify core API methods return dicts (not print)."""

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_status(self, mock_session, mock_post):
        from deye_core import get_status
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {
            "success": True,
            "deviceDataList": [{
                "deviceSn": "SN123",
                "dataList": [
                    {"key": "SOC", "value": "85", "unit": "%"},
                ],
            }],
        }
        result = get_status(env_path="dummy")
        assert result["success"] is True
        assert "SOC" in result["data"]

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_devices(self, mock_session, mock_post):
        from deye_core import get_devices
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.side_effect = [
            {"success": True, "stationList": [{"id": 1, "name": "Home"}]},
            {"success": True, "deviceListItems": [
                {"deviceSn": "SN123", "deviceType": "INVERTER"},
            ]},
        ]
        result = get_devices(env_path="dummy")
        assert result["success"] is True

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_history(self, mock_session, mock_post):
        from deye_core import get_history
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {
            "success": True,
            "dataList": [
                {"time": "1710300000", "itemList": [
                    {"key": "SOC", "value": "85", "unit": "%"},
                ]},
            ],
        }
        result = get_history(granularity=1, start="2026-03-13", end="2026-03-13", env_path="dummy")
        assert result["success"] is True
        assert len(result["data"]["records"]) == 1

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_alerts(self, mock_session, mock_post):
        from deye_core import get_alerts
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": True, "alertList": []}
        result = get_alerts(env_path="dummy")
        assert result["success"] is True

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_get_config(self, mock_session, mock_post):
        from deye_core import get_config
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": True, "batteryCapacity": 5120}
        result = get_config(section="battery", env_path="dummy")
        assert result["success"] is True

    @patch('deye_core.http_post')
    @patch('deye_core.get_session')
    def test_run_control_returns_order_id(self, mock_session, mock_post):
        from deye_core import run_control
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": True, "orderId": "ORD001"}
        result = run_control(action="set_solar_sell", params={"solarSell": 1}, env_path="dummy")
        assert result["success"] is True
        assert result["data"]["orderId"] == "ORD001"

    def test_check_setup_configured(self, tmp_path):
        from deye_core import check_setup
        env = tmp_path / ".env"
        env.write_text("DEYE_APP_ID=aid\nDEYE_EMAIL=e@m\n")
        result = check_setup(env_path=str(env))
        assert result["success"] is True
        assert result["data"]["status"] == "already_configured"
