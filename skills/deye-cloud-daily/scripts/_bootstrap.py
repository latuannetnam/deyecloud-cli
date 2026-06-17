"""Locate the shared deye_core module and make it importable.

Dependent skills (deye-cloud-daily, deye-cloud-monthly, ...) do:

    import _bootstrap   # noqa: F401  -- must precede `import deye_core`
    import deye_core

The deye-* skills are always installed together, so deye_core lives in a
sibling skill folder: <this-skill>/../deye-cloud/scripts/. Resolution order:

    1. $DEYE_CORE_DIR   -- explicit override (escape hatch)
    2. sibling          -- <this-skill>/../deye-cloud/scripts/
    3. fail loudly      -- non-zero exit naming the paths tried

This file is byte-identical across every dependent skill; the canonical
copy lives in skills/_template/scripts/_bootstrap.py. Python 3.8+ (no
PEP 604 unions).
"""
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

_CORE_MODULE = "deye_core"


def find_core_dir(start_file=None, environ=None):
    # type: (Optional[str], Optional[dict]) -> Optional[Path]
    """Return the directory containing deye_core.py, or None if not found."""
    if environ is None:
        environ = os.environ
    if start_file is None:
        start_file = __file__

    override = environ.get("DEYE_CORE_DIR")
    if override:
        cand = Path(override).expanduser()
        if (cand / (_CORE_MODULE + ".py")).is_file():
            return cand.resolve()

    script_dir = Path(start_file).parent.resolve()
    sibling = script_dir.parent.parent / "deye-cloud" / "scripts"
    if (sibling / (_CORE_MODULE + ".py")).is_file():
        return sibling.resolve()

    return None


def wants_json(argv=None):
    # type: (Optional[List[str]]) -> bool
    """True if the caller asked for JSON output."""
    if argv is None:
        argv = sys.argv[1:]
    if "--json" in argv or "--output=json" in argv or "-o=json" in argv:
        return True
    for i, tok in enumerate(argv):
        if tok in ("--output", "-o") and i + 1 < len(argv) and argv[i + 1] == "json":
            return True
    return False


def build_error(tried):
    # type: (List[Tuple[str, str]]) -> str
    """Human-readable message naming the paths tried and the remedy."""
    lines = [
        "deye_core.py not found. The deye-cloud suite must be installed together.",
        "Searched:",
    ]
    for label, path in tried:
        lines.append("  - {0}: {1}".format(label, path))
    lines.append(
        "Fix: install the whole skills/ suite together, or set $DEYE_CORE_DIR "
        "to the folder containing deye_core.py."
    )
    return "\n".join(lines)


def _tried_paths(start_file=None, environ=None):
    # type: (Optional[str], Optional[dict]) -> List[Tuple[str, str]]
    if environ is None:
        environ = os.environ
    if start_file is None:
        start_file = __file__
    script_dir = Path(start_file).parent.resolve()
    return [
        ("$DEYE_CORE_DIR", environ.get("DEYE_CORE_DIR") or "(unset)"),
        ("sibling", str(script_dir.parent.parent / "deye-cloud" / "scripts")),
    ]


def fail(tried, argv=None):
    # type: (List[Tuple[str, str]], Optional[List[str]]) -> None
    """Emit an actionable error (JSON if requested) and exit non-zero."""
    msg = build_error(tried)
    if wants_json(argv):
        import json
        sys.stdout.write(json.dumps({"error": msg}) + "\n")
    else:
        sys.stderr.write(msg + "\n")
    sys.exit(1)


def install(start_file=None, environ=None, argv=None):
    # type: (Optional[str], Optional[dict], Optional[List[str]]) -> Path
    """Locate the core dir and prepend it to sys.path; fail loudly if absent."""
    core_dir = find_core_dir(start_file=start_file, environ=environ)
    if core_dir is None:
        fail(_tried_paths(start_file=start_file, environ=environ), argv=argv)
    core_str = str(core_dir)
    if core_str not in sys.path:
        sys.path.insert(0, core_str)
    return core_dir


# Auto-run on import so `import _bootstrap` is all a script needs.
# Tests set DEYE_BOOTSTRAP_NOAUTO=1 to import the helpers in isolation.
if os.environ.get("DEYE_BOOTSTRAP_NOAUTO") != "1":
    install()
