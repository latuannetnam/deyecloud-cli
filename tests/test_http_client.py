"""Tests for HTTP client wrappers — stdlib urllib.request."""
import json
import os
import sys
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))
from deye_core import http_post, http_get


class TestHttpPost:
    @patch('deye_core.urlopen')
    def test_returns_parsed_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"success": True}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = http_post("http://example.com/api", {"key": "val"}, {"Authorization": "bearer tok"})
        assert result == {"success": True}

    @patch('deye_core.urlopen')
    def test_sends_json_body(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"success":true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        http_post("http://example.com/api", {"foo": "bar"}, {})
        req = mock_urlopen.call_args[0][0]
        assert json.loads(req.data) == {"foo": "bar"}


class TestHttpGet:
    @patch('deye_core.urlopen')
    def test_returns_parsed_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": 123}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = http_get("http://example.com/api/1", {"Authorization": "bearer tok"})
        assert result == {"data": 123}
