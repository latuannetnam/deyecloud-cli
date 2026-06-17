#!/usr/bin/env python3
"""Template analyzer — copy and rename for a new deye-* skill.

Demonstrates the standard two-line core bootstrap. Replace the body with
real logic that calls into deye_core.
"""
import argparse
import json

import _bootstrap  # noqa: F401  -- must precede `import deye_core`
import deye_core  # noqa: F401  -- the shared core (auth, session, API)


def main():
    parser = argparse.ArgumentParser(description="Template deye-* analyzer.")
    parser.add_argument("--output", "-o", choices=["text", "json"], default="text")
    args = parser.parse_args()

    result = {"status": "ok", "note": "replace this stub with real logic"}
    if args.output == "json":
        print(json.dumps(result))
    else:
        print("Template analyzer ready. Edit scripts/deye_example.py.")


if __name__ == "__main__":
    main()
