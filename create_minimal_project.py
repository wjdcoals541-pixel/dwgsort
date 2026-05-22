from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEST = ROOT / "project_minimal"

REQUIRED_FILES = [
    "cad_converter_qt.py",
    "DWGSort_4.0_실행.bat",
    "README.md",
    "dwgsort31/__init__.py",
    "dwgsort31/config.py",
    "dwgsort31/excel_compat.py",
    "dwgsort31/excel_compat3.3.py",
    "dwgsort31/excel_compat33.py",
    "dwgsort31/extended_save.py",
    "dwgsort31/pdf_lazy.py",
    "dwgsort31/pdf_point_filter.py",
    "dwgsort31/pdf_region_dialog.py",
    "dwgsort31/pdf_vector_parser.py",
    "dwgsort31/plotting.py",
    "dwgsort31/qt_app.py",
    "dwgsort31/qt_styles.py",
    "dwgsort31/qt_widgets.py",
    "dwgsort31/qt_workers.py",
    "dwgsort31/utils.py",
    "analyze_project_size.py",
    "create_minimal_project.py",
    "cleanup_candidates.md",
]

OPTIONAL_HOLD_FILES = [
    "videoframe_0.ico",
    "UI_HANDOFF_FOR_CLAUDE.md",
    "run.bat",
    "run_and_test.bat",
    "run_auto_reload.bat",
    "3.3은 점찍기 로직개선.txt",
    "결과__패치전.csv",
    "결과__패치후.csv",
    "dwgsort31/excel_compat__1.py",
    "dwgsort31/excel_compat__2.py",
]

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "project_minimal",
}

REQUIREMENTS = """PySide6
pandas
matplotlib
openpyxl
xlrd
PyMuPDF
"""

MINIMAL_README = """# DWGSort Minimal

This folder is a minimal runnable copy of the DWGSort 4.0 desktop app.

## Setup

```powershell
python -m venv .venv
.\\.venv\\Scripts\\activate
python -m pip install -r requirements.txt
python cad_converter_qt.py
```

Or run:

```powershell
.\\DWGSort_4.0_실행.bat
```

## Notes

- `.venv`, Git history, caches, generated result CSV files, and backup modules are not included.
- The legacy batch PDF path in `dwgsort31/pdf_lazy.py` looks for `..\\cad_converter_gui3.0.py`.
  That external file is outside the Git project and is not included in this minimal copy.
  The current vector-PDF region workflow lives inside `dwgsort31/pdf_region_dialog.py`
  and `dwgsort31/pdf_vector_parser.py`.
"""


def all_project_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
            continue
        if path.is_file():
            files.append(rel)
    return sorted(files, key=lambda item: item.as_posix().lower())


def copy_file(rel_text: str) -> bool:
    src = ROOT / rel_text
    if not src.exists():
        return False
    dst = DEST / rel_text
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main() -> None:
    if DEST.exists():
        raise SystemExit(f"Destination already exists: {DEST}")

    DEST.mkdir(parents=True)
    copied: list[str] = []
    missing: list[str] = []

    for rel in REQUIRED_FILES:
        if copy_file(rel):
            copied.append(rel)
        else:
            missing.append(rel)

    (DEST / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    (DEST / "README_MINIMAL.md").write_text(MINIMAL_README, encoding="utf-8")
    copied.extend(["requirements.txt", "README_MINIMAL.md"])

    required_set = {Path(item) for item in REQUIRED_FILES}
    hold_set = {Path(item) for item in OPTIONAL_HOLD_FILES}
    excluded: list[str] = []
    held: list[str] = []
    for rel in all_project_files():
        if rel in required_set:
            continue
        if rel in hold_set:
            held.append(str(rel))
        else:
            excluded.append(str(rel))

    print("Copied files:")
    for item in copied:
        print(f"  + {item}")

    if missing:
        print("\nMissing required files:")
        for item in missing:
            print(f"  ! {item}")

    print("\nExcluded files:")
    for item in excluded:
        print(f"  - {item}")

    print("\nHeld for manual review:")
    for item in held:
        print(f"  ? {item}")

    print(f"\nCreated: {DEST}")


if __name__ == "__main__":
    main()
