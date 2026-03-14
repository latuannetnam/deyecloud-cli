"""Tests for auth flow — password hashing, token management, device discovery."""
import hashlib
import json
import os
import sys
import time
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))
from deye_cli import _hash_password, _obtain_token, _discover_device, get_session


class TestHashPassword:
    def test_sha256(self):
        result = _hash_password("test123")
        assert result == hashlib.sha256(b"test123").hexdigest()


class TestObtainToken:
    @patch('deye_cli._http_post')
    def test_calls_token_endpoint(self, mock_post):
        mock_post.return_value = {"success": True, "accessToken": "tok", "expiresIn": 86400}
        result = _obtain_token("http://base", "appid", "secret", "e@m", "pass", "0")
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert "/account/token?appId=appid" in call_url
        assert result["accessToken"] == "tok"


class TestGetSession:
    def test_uses_cached_token_when_valid(self, tmp_path):
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
