"""Tests for MCP server — tool registration, parameter validation, and error handling."""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))


class TestMcpToolRegistration:
    """Verify all 7 tools are registered."""

    def test_server_has_seven_tools(self):
        from deye_mcp import mcp
        import asyncio
        tools = asyncio.run(mcp.list_tools())
        assert len(tools) == 7

    def test_expected_tool_names(self):
        from deye_mcp import mcp
        import asyncio
        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}
        expected = {"deye_status", "deye_history", "deye_devices",
                    "deye_alerts", "deye_config", "deye_control", "deye_setup"}
        assert tool_names == expected


class TestMcpStatusTool:
    """Verify deye_status tool calls core and returns structured result."""

    @patch('deye_core.get_session')
    @patch('deye_core.http_post')
    def test_status_returns_data(self, mock_post, mock_session):
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {
            "success": True,
            "deviceDataList": [{
                "deviceSn": "SN123",
                "dataList": [{"key": "SOC", "value": "85", "unit": "%"}],
            }],
        }
        from deye_mcp import deye_status
        import asyncio
        result = asyncio.run(deye_status())
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert "SOC" in parsed["data"]


class TestMcpParameterValidation:
    """Verify MCP tools validate parameters before calling core."""

    def test_history_invalid_granularity_raises_tool_error(self):
        from deye_mcp import deye_history
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="granularity"):
            asyncio.run(deye_history(
                granularity="hourly", start_date="2026-03-13", end_date="2026-03-13"
            ))

    def test_config_invalid_section_raises_tool_error(self):
        from deye_mcp import deye_config
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="section"):
            asyncio.run(deye_config(section="invalid"))

    def test_control_invalid_action_raises_tool_error(self):
        from deye_mcp import deye_control
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="action"):
            asyncio.run(deye_control(
                action="invalid_action", params={}, confirmed=True
            ))

    def test_devices_invalid_command_raises_tool_error(self):
        from deye_mcp import deye_devices
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="command"):
            asyncio.run(deye_devices(command="invalid"))

    def test_setup_invalid_command_raises_tool_error(self):
        from deye_mcp import deye_setup
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="command"):
            asyncio.run(deye_setup(command="invalid"))


class TestMcpControlTool:
    """Verify deye_control requires confirmation and returns focused diff."""

    @patch('deye_core.get_session')
    @patch('deye_core.http_post')
    def test_control_without_confirm_returns_diff(self, mock_post, mock_session):
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": True, "data": {"solarSell": 0, "workMode": 1}}
        from deye_mcp import deye_control
        import asyncio
        result = asyncio.run(deye_control(
            action="set_solar_sell", params={"action": "on"}, confirmed=False
        ))
        parsed = json.loads(result)
        assert parsed["confirmation_required"] is True
        assert "changes" in parsed


class TestMcpErrorHandling:
    """Verify API failures raise ToolError (isError=true in MCP protocol)."""

    @patch('deye_core.get_session')
    @patch('deye_core.http_post')
    def test_status_api_failure_raises_tool_error(self, mock_post, mock_session):
        mock_session.return_value = ("http://base", {"Authorization": "bearer tok"}, "SN123")
        mock_post.return_value = {"success": False, "msg": "Token expired", "code": 401}
        from deye_mcp import deye_status
        from fastmcp.exceptions import ToolError
        import asyncio
        with pytest.raises(ToolError, match="Token expired"):
            asyncio.run(deye_status())
