"""Build dist/finlit.zip: everything needed to install FinLit on another computer.

Usage (from the project folder):
    .venv\\Scripts\\python scripts\\package.py [--include-data]

The zip never contains .env (API keys), .venv (machine-specific) or caches.
--include-data also packs data/ (saved profiles, chat history, vector store).
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["pyproject.toml", "README.md", "CLAUDE.md", ".env.example", ".gitignore"]
FOLDERS = ["src", "tests", "docs", "scripts", ".vscode"]
SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def wanted(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    return not (parts & SKIP_DIRS or any(p.endswith(".egg-info") for p in parts) or path.suffix == ".pyc")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-data", action="store_true")
    args = parser.parse_args()

    folders = FOLDERS + (["data"] if args.include_data and (ROOT / "data").exists() else [])
    out = ROOT / "dist" / "finlit.zip"
    out.parent.mkdir(exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            if (ROOT / name).exists():
                zf.write(ROOT / name, f"finlit/{name}")
                count += 1
        for folder in folders:
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and wanted(path):
                    # as_posix keeps forward slashes so the zip extracts correctly on macOS/Linux too
                    zf.write(path, "finlit/" + path.relative_to(ROOT).as_posix())
                    count += 1
    print(f"Created {out} ({count} files, {out.stat().st_size / 1024:.0f} KB)")
    if args.include_data:
        print("Included data/ (profiles, chat history, vector store).")
    print("Your .env (API keys) was NOT included. Copy it separately and securely if you want the same keys.")


if __name__ == "__main__":
    main()
