#!/usr/bin/env python3
"""
bump_version.py – Update version number across all files in RoomFlow.

Usage:
    python3 scripts/bump_version.py 1.1.0
    python3 scripts/bump_version.py --patch   (1.0.0 → 1.0.1)
    python3 scripts/bump_version.py --minor   (1.0.0 → 1.1.0)
    python3 scripts/bump_version.py --major   (1.0.0 → 2.0.0)
"""

import json
import re
import sys
import subprocess
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
MANIFEST = ROOT / "custom_components" / "roomflow" / "manifest.json"
CONST_PY  = ROOT / "custom_components" / "roomflow" / "const.py"
HACS_JSON = ROOT / "hacs.json"


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_current_version() -> str:
    manifest = json.loads(MANIFEST.read_text())
    return manifest["version"]


def parse_version(version: str) -> tuple[int, int, int]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        print(f"❌  Invalid version format: '{version}'  (expected x.y.z)")
        sys.exit(1)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(current: str, bump_type: str) -> str:
    major, minor, patch = parse_version(current)
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        return bump_type  # explicit version string passed


def update_manifest(new_version: str):
    data = json.loads(MANIFEST.read_text())
    data["version"] = new_version
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"  ✅  manifest.json  → {new_version}")


def update_const(new_version: str):
    content = CONST_PY.read_text()
    updated = re.sub(
        r'(VERSION\s*=\s*)["\'][^"\']+["\']',
        f'\\g<1>"{new_version}"',
        content
    )
    if updated == content:
        print(f"  ⚠️   const.py — VERSION constant not found, skipping")
    else:
        CONST_PY.write_text(updated)
        print(f"  ✅  const.py       → {new_version}")


def git_tag_and_commit(new_version: str, auto_commit: bool):
    if not auto_commit:
        return

    tag = f"v{new_version}"
    try:
        subprocess.run(["git", "add",
                        str(MANIFEST.relative_to(ROOT)),
                        str(CONST_PY.relative_to(ROOT))],
                       cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"Release {tag}"],
                       cwd=ROOT, check=True)
        subprocess.run(["git", "tag", tag],
                       cwd=ROOT, check=True)
        print(f"\n  ✅  Git commit created")
        print(f"  ✅  Git tag created: {tag}")
        print(f"\n  👉  Push with:")
        print(f"      git push origin main")
        print(f"      git push origin {tag}")
    except subprocess.CalledProcessError as e:
        print(f"\n  ⚠️   Git operation failed: {e}")
        print(f"      Run manually:")
        print(f"      git add custom_components/roomflow/manifest.json custom_components/roomflow/const.py")
        print(f"      git commit -m 'Release v{new_version}'")
        print(f"      git tag v{new_version}")
        print(f"      git push origin main && git push origin v{new_version}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    current = get_current_version()
    print(f"\nCurrent version: {current}")

    # Determine new version
    arg = args[0].lstrip("-")  # strip -- prefix
    if arg in ("patch", "minor", "major"):
        new_version = bump_version(current, arg)
    else:
        new_version = args[0].lstrip("v")  # allow "v1.2.3" or "1.2.3"
        parse_version(new_version)  # validate format

    if new_version == current:
        print(f"❌  New version is the same as current ({current}). Nothing to do.")
        sys.exit(1)

    print(f"New version:     {new_version}\n")

    # Confirm
    confirm = input(f"Update all files from {current} → {new_version}? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    print("\nUpdating files...")
    update_manifest(new_version)
    update_const(new_version)

    # Ask about git
    print()
    git_confirm = input("Create git commit and tag automatically? [y/N] ").strip().lower()
    git_tag_and_commit(new_version, git_confirm == "y")

    print(f"\n🎉  Done! Version bumped to {new_version}")


if __name__ == "__main__":
    main()
