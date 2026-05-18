#!/usr/bin/env python3
"""Thin demo: skill catalog + load_skill via the integrated agent modules."""

from skills import get_registry
from tools.load_skill import run_load_skill

if __name__ == "__main__":
    registry = get_registry()
    print("Skills directory:", registry.skills_dir)
    print("\nAvailable:\n", registry.describe_available(), sep="")
    while True:
        try:
            name = input("\nskill name (empty to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not name:
            break
        print(run_load_skill(name))
