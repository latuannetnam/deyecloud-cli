---
name: deye-cloud-EXAMPLE
description: >-
  TEMPLATE — replace this. Describe when the agent should use this skill, with
  concrete trigger phrases. Keep frontmatter to name + description only.
---

# deye-cloud-EXAMPLE (template)

Copy this folder to `skills/deye-cloud-<x>/`, then edit the frontmatter and
`scripts/deye_<x>.py`. The suite installs together, so the shared core is found
automatically via `_bootstrap.py`.

## Running scripts

This skill ships Python scripts in its own `scripts/` folder. Invoke them with:

- **Claude Code:** `python3 "${CLAUDE_SKILL_DIR}/scripts/<file>.py" ...`
- **Other harnesses (Antigravity, Codex, Gemini, Copilot):** the skill directory
  is the folder containing this `SKILL.md`. Run
  `python3 <skill-dir>/scripts/<file>.py ...` — e.g. from the repo that is
  `python3 skills/<this-skill>/scripts/<file>.py ...`.

Scripts self-locate both the shared core and the `.env`, so there are no
working-directory assumptions — you only need to run the correct `.py` file.

## Workflow

1. Parse the user's request.
2. Run `python3 "${CLAUDE_SKILL_DIR}/scripts/deye_example.py" --output text`.
3. Present the result.

## Script Location & Dependencies

- **Script:** `scripts/deye_example.py`
- **Reuses:** `deye-cloud/scripts/deye_core.py` (located via `_bootstrap.py`)
- **Dependencies:** stdlib only
