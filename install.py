#!/usr/bin/env python3
"""Cross-platform installer for the deye-* skill suite.

Installs every skill under skills/ (skipping _-prefixed folders) into a
harness skills directory. Source of truth for install logic; install-skill.ps1
and install.sh are thin wrappers around this. Python 3.8+ (no PEP 604 unions).

Usage:
    python install.py [--scope local|global] [--target PATH] [--list] [--dry-run]
"""
import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Optional

_REPO_ROOT = Path(__file__).parent.resolve()
_SKILLS_ROOT = _REPO_ROOT / "skills"


def discover_skills(skills_root):
    # type: (Path) -> List[Path]
    """Return installable skill dirs: not _-prefixed, containing a SKILL.md."""
    out = []
    for child in sorted(skills_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            continue
        if (child / "SKILL.md").is_file():
            out.append(child)
    return out


def resolve_base(scope, target):
    # type: (str, Optional[str]) -> Path
    """Resolve the base dir; skills land in <base>/.claude/skills/."""
    if target:
        return Path(target).expanduser().resolve()
    if scope == "global":
        return Path.home()
    return Path.cwd()


def install_skill(skill_dir, skills_dest, dry_run=False):
    # type: (Path, Path, bool) -> bool
    """Copy SKILL.md + references/ + scripts/ into skills_dest/<name>/."""
    name = skill_dir.name
    dest = skills_dest / name

    src_skill_md = skill_dir / "SKILL.md"
    if not src_skill_md.is_file():
        print("  [ERR] {0}: SKILL.md not found".format(name))
        return False

    if dry_run:
        print("  [DRY] would install {0} -> {1}".format(name, dest))
        return True

    if dest.exists():
        shutil.rmtree(dest)
    (dest / "scripts").mkdir(parents=True, exist_ok=True)

    shutil.copy2(src_skill_md, dest / "SKILL.md")

    src_scripts = skill_dir / "scripts"
    if src_scripts.is_dir():
        for f in sorted(src_scripts.glob("*.py")):
            shutil.copy2(f, dest / "scripts" / f.name)

    src_refs = skill_dir / "references"
    if src_refs.is_dir():
        (dest / "references").mkdir(parents=True, exist_ok=True)
        for f in sorted(src_refs.glob("*.md")):
            shutil.copy2(f, dest / "references" / f.name)

    print("  [OK]  {0} -> {1}".format(name, dest))
    return True


def main(argv=None):
    # type: (Optional[List[str]]) -> int
    parser = argparse.ArgumentParser(description="Install the deye-* skill suite.")
    parser.add_argument("--scope", choices=["local", "global"], default="global",
                        help="global -> ~/.claude/skills, local -> ./.claude/skills")
    parser.add_argument("--target", default=None,
                        help="explicit base dir (overrides --scope default)")
    parser.add_argument("--list", action="store_true",
                        help="list discoverable skills and the resolved dest, then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be copied without writing")
    args = parser.parse_args(argv)

    if not _SKILLS_ROOT.is_dir():
        print("[ERR] skills/ not found at {0}".format(_SKILLS_ROOT), file=sys.stderr)
        return 1

    skills = discover_skills(_SKILLS_ROOT)
    if not skills:
        print("[ERR] no installable skills under {0}".format(_SKILLS_ROOT),
              file=sys.stderr)
        return 1

    base = resolve_base(args.scope, args.target)
    skills_dest = base / ".claude" / "skills"

    print("Skills      : {0}".format(", ".join(s.name for s in skills)))
    print("Destination : {0}".format(skills_dest))

    if args.list:
        return 0

    ok, failed = [], []
    for skill in skills:
        if install_skill(skill, skills_dest, dry_run=args.dry_run):
            ok.append(skill.name)
        else:
            failed.append(skill.name)

    print("")
    print("Installed   : {0}".format(", ".join(ok) if ok else "(none)"))
    if failed:
        print("Failed      : {0}".format(", ".join(failed)))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
