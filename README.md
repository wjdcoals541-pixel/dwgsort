# DWGSort

DWGSort is a Python desktop tool for organizing and processing CAD/DWG-related data with Excel and PDF support.

The repository keeps version snapshots in Git history:

- `v3.1`: first committed version
- `v3.2`: intermediate 3.2 version
- `v3.3`: latest version

## Folder Structure

```text
.
+-- dwgsort31/                 # Main application package
|   +-- __init__.py            # Package marker
|   +-- config.py              # App configuration values
|   +-- excel_compat.py        # Excel compatibility and parsing logic
|   +-- excel_compat3.3.py     # Version 3.3 Excel compatibility experiment
|   +-- excel_compat33.py      # Version 3.3 helper/backup module
|   +-- excel_compat__1.py     # Previous Excel compatibility backup
|   +-- excel_compat__2.py     # Previous Excel compatibility backup
|   +-- extended_save.py       # Extended save/export helpers
|   +-- pdf_lazy.py            # Lazy PDF loading helpers
|   +-- plotting.py            # Plotting/point logic helpers
|   +-- qt_app.py              # Main Qt application window and UI flow
|   +-- qt_styles.py           # Qt stylesheet definitions
|   +-- qt_widgets.py          # Custom Qt widgets
|   +-- qt_workers.py          # Background worker logic
|   +-- utils.py               # Shared utility functions
+-- cad_converter_qt.py        # Qt app entry point
+-- run.bat                    # Basic Windows run script
+-- run_and_test.bat           # Run script with test/check flow
+-- run_auto_reload.bat        # Auto-reload run helper
+-- videoframe_0.ico           # Application icon
+-- UI_HANDOFF_FOR_CLAUDE.md   # UI handoff notes
+-- 결과__패치전.csv             # Sample/result data before patch
+-- 결과__패치후.csv             # Sample/result data after patch
+-- 3.3은 점찍기 로직개선.txt      # Note marking the 3.3 point-logic change
```

## Ignored Local Files

The following local/generated folders are intentionally not tracked:

- `.venv/`
- `build/`
- `dist/`
- `trash/`
- `3.0error/`
- `__pycache__/`
- generated `.exe` files

These can be recreated locally and should not be committed to GitHub.

## Version History

To view a saved version:

```bash
git checkout v3.1
git checkout v3.2
git checkout v3.3
```

To return to the latest development branch:

```bash
git checkout main
```
