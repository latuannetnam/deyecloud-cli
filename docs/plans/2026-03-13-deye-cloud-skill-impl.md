# Deye Cloud Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete Antigravity skill for managing Deye Hybrid Inverters — CLI script, reference docs, and SKILL.md.

**Architecture:** Single stdlib-only Python CLI (`deye_cli.py`) with 28 subcommands, wrapped by a rich skill (SKILL.md + references). Auth logic ported from `samples/deye_auth.py`, history logic from `samples/deye_history.py`, measure-points from `samples/deye_measure_points.py`. All `requests`/`dotenv` replaced with `urllib.request` and custom `.env` parsers.

**Tech Stack:** Python 3.10+ stdlib only (`urllib.request`, `json`, `hashlib`, `argparse`, `pathlib`), pytest for tests.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `skills/deye-cloud/SKILL.md` (empty placeholder)
- Create: `skills/deye-cloud/scripts/deye_cli.py` (empty placeholder)
- Create: `skills/deye-cloud/references/api-overview.md` (empty placeholder)
- Create: `skills/deye-cloud/references/monitoring.md` (empty placeholder)
- Create: `skills/deye-cloud/references/configuration.md` (empty placeholder)
- Create: `skills/deye-cloud/references/control.md` (empty placeholder)
- Create: `tests/test_env_parser.py` (empty placeholder)
- Create: `tests/test_http_client.py` (empty placeholder)
- Create: `tests/test_auth.py` (empty placeholder)
- Create: `tests/test_cli_commands.py` (empty placeholder)

**Step 1: Create directory structure**

```bash
mkdir -p skills/deye-cloud/scripts skills/deye-cloud/references tests
touch skills/deye-cloud/SKILL.md
touch skills/deye-cloud/scripts/deye_cli.py
touch skills/deye-cloud/references/api-overview.md
touch skills/deye-cloud/references/monitoring.md
touch skills/deye-cloud/references/configuration.md
touch skills/deye-cloud/references/control.md
touch tests/__init__.py tests/test_env_parser.py tests/test_http_client.py
touch tests/test_auth.py tests/test_cli_commands.py
```

**Step 2: Commit**

```bash
git add skills/ tests/
git commit -m "chore: scaffold deye-cloud skill directory structure"
```

---

### Task 2: .env Parser (Section 1)

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`
- Test: `tests/test_env_parser.py`

**Step 1: Write failing tests for `_load_env` and `_save_env`**

```python
# tests/test_env_parser.py
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
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_env_parser.py -v
```

Expected: FAIL — `ImportError: cannot import name '_load_env'`

**Step 3: Implement `_load_env()` and `_save_env()` in `deye_cli.py`**

```python
#!/usr/bin/env python3
"""Deye Cloud CLI — Zero-dependency inverter management."""

import os
from pathlib import Path

# ── Section 1: .env Parser ─────────────────────────────
_DEFAULT_ENV_PATH = os.path.join(Path.home(), '.deye', '.env')


def _load_env(path: str) -> dict:
    """Read a .env file, return dict. Skip comments/blanks, split on first =, strip quotes."""
    env = {}
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Strip surrounding quotes
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                env[key] = value
    except FileNotFoundError:
        pass
    return env


def _save_env(path: str, updates: dict) -> None:
    """Update/add keys in a .env file, preserving comments and order."""
    lines = []
    seen = set()
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            for line in fh:
                raw = line.rstrip('\n').rstrip('\r')
                stripped = raw.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    key = stripped.split('=', 1)[0].strip()
                    if key in updates:
                        lines.append(f"{key}={updates[key]}")
                        seen.add(key)
                        continue
                lines.append(raw)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)

    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/test_env_parser.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add skills/deye-cloud/scripts/deye_cli.py tests/test_env_parser.py
git commit -m "feat: add .env parser (_load_env, _save_env)"
```

---

### Task 3: HTTP Client (Section 2)

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`
- Test: `tests/test_http_client.py`

**Step 1: Write failing tests for `_http_post` and `_http_get`**

```python
# tests/test_http_client.py
"""Tests for HTTP client wrappers — stdlib urllib.request."""
import json
import os
import sys
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'deye-cloud', 'scripts'))
from deye_cli import _http_post, _http_get


class TestHttpPost:
    @patch('deye_cli.urlopen')
    def test_returns_parsed_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"success": True}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _http_post("http://example.com/api", {"key": "val"}, {"Authorization": "bearer tok"})
        assert result == {"success": True}

    @patch('deye_cli.urlopen')
    def test_sends_json_body(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"success":true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        _http_post("http://example.com/api", {"foo": "bar"}, {})
        req = mock_urlopen.call_args[0][0]
        assert json.loads(req.data) == {"foo": "bar"}


class TestHttpGet:
    @patch('deye_cli.urlopen')
    def test_returns_parsed_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": 123}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _http_get("http://example.com/api/1", {"Authorization": "bearer tok"})
        assert result == {"data": 123}
```

**Step 2: Run tests to verify fail**

```bash
pytest tests/test_http_client.py -v
```

**Step 3: Implement `_http_post()` and `_http_get()`**

```python
# Add to deye_cli.py — Section 2
import json
from urllib.request import Request, urlopen

_TIMEOUT = 15

def _http_post(url: str, payload: dict, headers: dict) -> dict:
    """POST JSON, return parsed response dict."""
    data = json.dumps(payload).encode('utf-8')
    hdrs = {**headers, 'Content-Type': 'application/json'}
    req = Request(url, data=data, headers=hdrs, method='POST')
    with urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


def _http_get(url: str, headers: dict) -> dict:
    """GET request, return parsed response dict."""
    req = Request(url, headers=headers, method='GET')
    with urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/test_http_client.py -v
```

**Step 5: Commit**

```bash
git add skills/deye-cloud/scripts/deye_cli.py tests/test_http_client.py
git commit -m "feat: add HTTP client wrappers (_http_post, _http_get)"
```

---

### Task 4: Auth Module (Section 3)

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`
- Test: `tests/test_auth.py`
- Reference: `samples/deye_auth.py` (port logic from here)

**Step 1: Write failing tests**

```python
# tests/test_auth.py
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
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_auth.py -v
```

**Step 3: Implement auth functions** — port from `samples/deye_auth.py`, replacing `requests` with `_http_post`, `dotenv` with `_load_env`/`_save_env`. Key functions: `_hash_password()`, `_obtain_token()`, `_discover_device()`, `get_session(env_path=None)`.

**Step 4: Run tests**

```bash
pytest tests/test_auth.py -v
```

**Step 5: Commit**

```bash
git add skills/deye-cloud/scripts/deye_cli.py tests/test_auth.py
git commit -m "feat: add auth module (token, device discovery)"
```

---

### Task 5: Output Formatting (Section 7)

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`

**Step 1: Implement `_json_output()`, `_human_output()`, `_format_timestamp()`**

```python
import sys
from datetime import datetime, timezone, timedelta

_LOCAL_TZ = timezone(timedelta(hours=7))  # UTC+7

def _format_timestamp(raw) -> str:
    try:
        return datetime.fromtimestamp(int(raw), tz=_LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return str(raw)

def _json_output(success: bool, command: str, device_sn: str, data=None, error=None, api_code=None, api_msg=None):
    out = {
        "success": success,
        "command": command,
        "device_sn": device_sn,
        "timestamp": datetime.now(tz=_LOCAL_TZ).isoformat(),
    }
    if success:
        out["data"] = data
    else:
        out["error"] = error
        if api_code: out["api_code"] = api_code
        if api_msg: out["api_msg"] = api_msg
    print(json.dumps(out, indent=2, ensure_ascii=False))

def _human_output(title: str, data: dict, indent: int = 0):
    prefix = "  " * indent
    print(f"\n{prefix}{'='*60}")
    print(f"{prefix}  {title}")
    print(f"{prefix}{'='*60}")
    for key, val in data.items():
        if isinstance(val, dict):
            print(f"{prefix}  {key}:")
            for k2, v2 in val.items():
                print(f"{prefix}    {k2}: {v2}")
        else:
            print(f"{prefix}  {key}: {val}")
```

**Step 2: Commit**

```bash
git add skills/deye-cloud/scripts/deye_cli.py
git commit -m "feat: add output formatters (JSON + human)"
```

---

### Task 6: CLI Entry Point + `setup` Command (Section 8)

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`
- Test: `tests/test_cli_commands.py`

**Step 1: Write failing test for `setup` subcommand**

```python
# tests/test_cli_commands.py
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
```

**Step 2: Run test to verify fail**

```bash
pytest tests/test_cli_commands.py::TestSetup -v
```

**Step 3: Implement argparse setup + `cmd_setup()` function** — create the full argparse skeleton with all global flags (`--json`, `--device-sn`, `--env-path`) and one initial subcommand `setup`. The `setup` command validates or creates `~/.deye/.env` with a template.

**Step 4: Run test**

```bash
pytest tests/test_cli_commands.py::TestSetup -v
```

**Step 5: Commit**

```bash
git add skills/deye-cloud/scripts/deye_cli.py tests/test_cli_commands.py
git commit -m "feat: add CLI entry point + setup command"
```

---

### Task 7: Monitor Commands — `status`, `devices`, `measure-points`

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`
- Test: `tests/test_cli_commands.py` (add `TestStatus`, `TestDevices`)

**Step 1: Write failing tests** — mock `_http_post` to return sample JSON, verify CLI output

**Step 2: Implement `cmd_status()`, `cmd_devices()`, `cmd_measure_points()`** — port logic from `samples/deye_measure_points.py` using `_http_post`, route via argparse subcommands

**Step 3: Run tests, commit**

```bash
pytest tests/test_cli_commands.py -v
git add -A && git commit -m "feat: add monitor commands (status, devices, measure-points)"
```

---

### Task 8: Monitor Commands — `history`, `history-raw`, `alerts`, `order-status`

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`

**Step 1: Write failing tests** — test `history` with `--granularity`, `--start`, `--end`, `--points` args

**Step 2: Implement** — port from `samples/deye_history.py`, add `history-raw`, `alerts`, `order-status`

**Step 3: Run tests, commit**

```bash
pytest tests/test_cli_commands.py -v
git add -A && git commit -m "feat: add history, alerts, order-status commands"
```

---

### Task 9: Monitor Commands — `station-*`

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`

**Step 1: Write tests + implement** — `station-list`, `station-info`, `station-history`, `station-alerts`

**Step 2: Run tests, commit**

```bash
pytest tests/ -v
git add -A && git commit -m "feat: add station commands"
```

---

### Task 10: Config Commands

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`

**Step 1: Write tests + implement** — `config-battery`, `config-system`, `config-tou`, `dynamic-read` (two-step: POST read → poll readResult)

**Step 2: Run tests, commit**

```bash
pytest tests/ -v
git add -A && git commit -m "feat: add config commands (battery, system, tou, dynamic-read)"
```

---

### Task 11: Control Commands

**Files:**
- Modify: `skills/deye-cloud/scripts/deye_cli.py`

**Step 1: Write tests + implement** — All 13 `set-*` and `dynamic-control` commands. Each one sends a POST to the appropriate `/order/*` or `/strategy/*` endpoint. All return an `orderId` for tracking.

**Step 2: Run tests, commit**

```bash
pytest tests/ -v
git add -A && git commit -m "feat: add control commands (13 set-* subcommands)"
```

---

### Task 12: Reference Documents

**Files:**
- Write: `skills/deye-cloud/references/api-overview.md`
- Write: `skills/deye-cloud/references/monitoring.md`
- Write: `skills/deye-cloud/references/configuration.md`
- Write: `skills/deye-cloud/references/control.md`

**Step 1: Write `api-overview.md`** — Base URLs, auth flow (SHA256), token lifecycle, response envelope, rate limits.

**Step 2: Write `monitoring.md`** — Measure point code table, history granularity, date formats, alert codes.

**Step 3: Write `configuration.md`** — Battery parameter ranges, work modes, TOU structure, dynamic read flow.

**Step 4: Write `control.md`** — Enum values per command, order execution flow (send → orderId → poll), safety warnings, device compatibility.

**Step 5: Commit**

```bash
git add skills/deye-cloud/references/
git commit -m "docs: add reference documents (api, monitoring, config, control)"
```

---

### Task 13: SKILL.md

**Files:**
- Write: `skills/deye-cloud/SKILL.md`

**Step 1: Write SKILL.md** with YAML frontmatter, workflow instructions, command catalog, safety protocol (from design §6), and references. Key sections:
- Frontmatter: `name: deye-cloud`, `description: ...`
- First-run setup workflow
- Command catalog (grouped by Monitor/Config/Control)
- Safety protocol (mandatory read-before-write, comparison table, user confirmation)
- Reference links
- Troubleshooting

**Step 2: Commit**

```bash
git add skills/deye-cloud/SKILL.md
git commit -m "docs: add SKILL.md with full workflow and safety rules"
```

---

### Task 14: Integration Test (Live API)

**Files:**
- No new files — manual testing with real credentials

**Step 1: Run setup**

```bash
python skills/deye-cloud/scripts/deye_cli.py --json setup
```

Expected: Creates `~/.deye/.env` template or validates existing one.

**Step 2: Test auth + status**

```bash
python skills/deye-cloud/scripts/deye_cli.py --json status
```

Expected: JSON with live PV, battery, grid, consumption data.

**Step 3: Test history**

```bash
python skills/deye-cloud/scripts/deye_cli.py --json history --granularity 1 --start 2026-03-13 --end 2026-03-13
```

Expected: Intraday 5-minute readings for today.

**Step 4: Test config read**

```bash
python skills/deye-cloud/scripts/deye_cli.py --json config-battery
```

Expected: Battery capacity, SOC limits, charge/discharge current.

**Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

**Step 6: Final commit**

```bash
git add -A && git commit -m "feat: complete deye-cloud skill v1.0"
```

---

## Verification Plan

### Automated Tests

All tests use `pytest` and run via:

```bash
pytest tests/ -v
```

| Test File | Coverage |
|-----------|----------|
| `tests/test_env_parser.py` | `_load_env`, `_save_env` — file I/O, quotes, comments, special chars |
| `tests/test_http_client.py` | `_http_post`, `_http_get` — mocked `urlopen`, JSON encoding |
| `tests/test_auth.py` | `_hash_password`, `_obtain_token`, `get_session` — token caching logic |
| `tests/test_cli_commands.py` | CLI subcommands via `subprocess.run` — `setup`, `status` |

### Manual Verification (requires real Deye Cloud credentials)

1. **Setup**: Run `deye_cli.py setup` → should validate or create `~/.deye/.env`
2. **Auth**: Run `deye_cli.py --json status` → should authenticate and return live data
3. **History**: Run `deye_cli.py --json history --granularity 2 --start 2026-03-01 --end 2026-03-13` → should return daily totals
4. **Config**: Run `deye_cli.py --json config-battery` → should return battery settings
5. **Human mode**: Run `deye_cli.py status` (no `--json`) → should print human-readable table

> [!WARNING]
> **Do NOT test control commands (`set-*`) without explicit user permission.** These modify real inverter settings.
