# Multi-Harness Skill Portability — Design

**Date:** 2026-06-17
**Status:** Approved (pending spec review)
**Topic:** Make the deye-* skill suite run cleanly across multiple AI agent harnesses and from a local folder (repo-as-is or per-project install), without duplicating the shared core.

---

## 1. Goals & Constraints

### Goals
1. **Multi-harness ready** — skills run on Claude Code, Antigravity, and Codex / Gemini / Copilot CLI without per-harness edits.
2. **Run from a local folder** — the suite works two ways:
   - **Repo-as-is:** point a harness at this repo's `skills/` folder; no install step.
   - **Per-project / global install:** a cross-platform installer copies the suite into a project's local `.claude/skills/` or the global `~/.claude/skills/`.
3. **Reusable core, modular skills** — keep one `deye_core.py` (single source of truth) while skills stay separate folders organized by function.
4. **Extensible** — adding a new deye-* skill is a mechanical, documented step.

### Constraints / Decisions
- The deye-* skills are a **suite, always installed and used together.** There is no scenario where a user installs only `deye-cloud-daily` or only `deye-cloud-monthly`. This removes the need for per-skill vendoring of the core.
- Target harnesses are **CLI-based** (load `SKILL.md` from a folder). Claude Desktop MCP is out of scope for this change (the existing `deye_mcp.py` is untouched).
- `deye_core.py` remains the foundational module living in `deye-cloud/scripts/`. Other skills are pure consumers.

---

## 2. Problem Statement

Today the suite has four portability blockers:

1. **`${CLAUDE_SKILL_DIR}` is Claude-Code-only.** `deye-cloud/SKILL.md` mixes it (lines 66, 127, 170) with repo-root-relative paths like `skills/deye-cloud/scripts/...` (line 13). Non-Claude harnesses won't substitute the variable.
2. **Inconsistent invocation paths across the three SKILL.md files.** `deye-cloud` uses the env var; `deye-cloud-daily` / `deye-cloud-monthly` use `skills/<name>/scripts/...` which only resolves from the repo root.
3. **Hidden cross-skill coupling.** `deye_daily.py` / `deye_monthly.py` import `deye_core.py` via `../../deye-cloud/scripts/` with no override and an unhelpful failure mode (raw `ImportError`).
4. **Installer is PowerShell-only (Windows) and global-only** (`~/.claude/skills/`). No first-class local/per-project install, no cross-platform path.

---

## 3. Architecture

The solution has two halves: **core resolution** (how a script finds the shared core) and **invocation** (how the agent finds the script).

### Half 1 — Core resolution via `_bootstrap.py`

Each dependent skill's `scripts/` folder contains a small `_bootstrap.py`. `deye_daily.py` and `deye_monthly.py` do `import _bootstrap` **before** `import deye_core`. The bootstrap locates the core directory and inserts it into `sys.path`, searching in order:

1. **`$DEYE_CORE_DIR`** — explicit override (escape hatch for unusual layouts).
2. **Sibling skill** — `<this-skill>/../deye-cloud/scripts/`. Works in every real layout because the suite is always installed together under a shared parent: repo `skills/`, global `~/.claude/skills/`, project `.claude/skills/`.
3. **Fail loudly** — if the core is not found, exit non-zero with an actionable message listing the paths tried and the fix ("install the deye-cloud suite together" / "set `$DEYE_CORE_DIR`"). When the caller requested JSON output, emit `{"error": "..."}`.

`_bootstrap.py` is **byte-identical** across all dependent skills (they all resolve the same `../deye-cloud/scripts/` core), so it is a stable copy-once file, not bespoke per skill. The canonical copy lives in `skills/_template/scripts/_bootstrap.py`.

**What this adds over today's inline `parent.parent / "deye-cloud"` line:** an env override and a clear failure message instead of a raw `ImportError`. No vendoring, no `_vendor/` directory (rejected as YAGNI given the suite-only constraint).

### Half 2 — Harness-agnostic invocation

Standardize all three SKILL.md files on **one token plus a short "Running scripts" preamble**:

- **Claude Code:** `python3 "${CLAUDE_SKILL_DIR}/scripts/<file>.py" ...`
- **Antigravity / Codex / Gemini / Copilot:** the skill directory is the folder containing this `SKILL.md` → `python3 <skill-dir>/scripts/<file>.py ...`. When running from the repo that is `skills/<name>/scripts/...`.

The preamble states this once near the top of each SKILL.md; the rest of the body uses the `${CLAUDE_SKILL_DIR}/scripts/<file>.py` form consistently. Because scripts self-locate both the core (Half 1) and the `.env` (existing `DEFAULT_ENV_PATH` logic), the only requirement on the agent is "run the right `.py` file" — there are no CWD assumptions.

### Runtime data flow

```
agent
  -> reads SKILL.md
  -> runs: python3 <skill-dir>/scripts/deye_X.py --json ...
       -> import _bootstrap            (locate core dir: env -> sibling -> error)
       -> import deye_core
       -> deye_core resolves .env      ($DEYE_ENV_PATH -> cwd/.env -> ~/.deye/.env)
       -> DeyeCloud API
```

---

## 4. Components

| Component | Change | Notes |
|-----------|--------|-------|
| `skills/deye-cloud/scripts/deye_core.py` | unchanged | Single reusable core; remains source of truth |
| `skills/deye-cloud-daily/scripts/_bootstrap.py` | **new** | Core locator (copy of canonical) |
| `skills/deye-cloud-monthly/scripts/_bootstrap.py` | **new** | Core locator (copy of canonical) |
| `skills/deye-cloud-daily/scripts/deye_daily.py` | edit | Replace ad-hoc sibling insert with `import _bootstrap` |
| `skills/deye-cloud-monthly/scripts/deye_monthly.py` | edit | Same |
| `skills/deye-cloud/SKILL.md` | edit | Add "Running scripts" preamble; normalize all invocation strings |
| `skills/deye-cloud-daily/SKILL.md` | edit | Same; replace `skills/<name>/...` strings |
| `skills/deye-cloud-monthly/SKILL.md` | edit | Same |
| `skills/_template/` | **new** | Scaffold for adding skills (SKILL.md skeleton, `scripts/_bootstrap.py`, stub analyzer) |
| `install.py` | **new** | Cross-platform installer (source of truth for install logic) |
| `install-skill.ps1` | edit | Becomes a thin wrapper that calls `python install.py ...` |
| `install.sh` | **new** | Thin wrapper for macOS/Linux |
| `tests/test_bootstrap.py` | **new** | Core-resolution tests |
| `tests/test_install.py` | **new** | Installer tests |
| `README.md` | edit | Document run modes, per-harness invocation, "Adding a new skill" recipe |

---

## 5. Installer (`install.py`)

```
python install.py [--scope local|global] [--target PATH] [--list] [--dry-run]
```

- `--scope global` (default) → installs to `~/.claude/skills/<name>/` (current behavior).
- `--scope local` → installs to `<target>/.claude/skills/<name>/`; default `target` = current working directory (per-project install).
- `--target PATH` → explicit destination root; overrides the scope default.
- `--list` → list discoverable skills and the resolved destination, then exit.
- `--dry-run` → print what would be copied without writing.

**Behavior:**
- Always installs the **entire suite** (every folder under `skills/`). No per-skill subsetting, no vendoring flag.
- **Skips `_`-prefixed folders** (`_template/`, future `_shared/`) so they are never installed as skills.
- For each skill, copies `SKILL.md`, `references/` (if present), and `scripts/` (including `_bootstrap.py`). Files are copied **as-is** (matches the current PS1 behavior — no frontmatter rewriting in this change).
- Uses `pathlib` throughout for Windows/macOS/Linux correctness.
- Removes only the specific `<dest>/skills/<name>/` target dir before re-copying; never touches unrelated files.
- Clear per-skill status output and a final summary.

`install-skill.ps1` and `install.sh` become thin wrappers (resolve script dir, call `python install.py "$@"`) so existing Windows usage keeps working.

---

## 6. Extensibility

Adding a new deye-* skill is mechanical:

1. `cp -r skills/_template skills/deye-cloud-<x>`
2. Edit the new `SKILL.md` `name` / `description`; write `scripts/<x>.py` (the stub already does `import _bootstrap; import deye_core`).
3. Run `install.py` (or just point a harness at the repo).

The new skill inherits core reuse, multi-harness invocation, and installer pickup for free. No installer code changes are required (auto-discovery). `_bootstrap.py` comes from the template and is identical to the other skills' copies. The README documents this recipe.

---

## 7. Error Handling

- **Bootstrap, core not found:** non-zero exit; human-readable message naming the search paths tried and the remediation. If the script was invoked with a JSON-output flag, emit `{"error": "..."}` so agents parse it cleanly.
- **Installer, missing source:** validate `skills/` exists and contains at least one non-`_` folder; clear error otherwise.
- **Installer, unwritable target:** surface the path and the OS error; do not partially clobber an existing install (remove-then-copy is per-skill and only after source is validated).
- **Existing runtime errors** (auth, device-not-found, API) are unchanged — handled in `deye_core.py` as today.

---

## 8. Testing

- **`tests/test_bootstrap.py`** — build temp directory layouts and assert core resolution:
  - sibling `deye-cloud/scripts/` present → resolves to it.
  - `$DEYE_CORE_DIR` set → wins over sibling.
  - neither present → clean error + non-zero exit (and `{"error"}` in JSON mode).
- **`tests/test_install.py`** — run `install.py --scope local --target <tmp>`:
  - suite lands in `<tmp>/.claude/skills/<name>/` for each non-`_` skill.
  - `_template/` is **not** installed.
  - `--dry-run` writes nothing.
- **Regression:** existing 42 tests (`test_core`, `test_cli_commands`, `test_mcp`, `test_auth`, `test_env_parser`, `test_http_client`) stay green — core/CLI/MCP logic is untouched.
- Tests use `pathlib` + `tmp_path`; no OS-specific assumptions so they pass on Windows/macOS/Linux.

---

## 9. Out of Scope

- No pip-installable package / console entry points (Approach B). May be added later as an optional convenience.
- No changes to MCP server (`deye_mcp.py`) or Claude Desktop deployment.
- No frontmatter-stripping logic in the installer (kept as copy-as-is, matching current PS1 behavior).
- No new runtime dependencies (stdlib only; `fastmcp` remains MCP-only).
