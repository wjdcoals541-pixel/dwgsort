# DWGSort Project Cleanup Report

## Summary

- Project root: `E:\ai\pythonpythonpython\dwgsort\dwgsort`
- Current execution entry: `python cad_converter_qt.py`
- Windows launcher: `DWGSort_4.0_실행.bat`
- Total observed size including `.venv`: about `880.50 MB`
- Source/application size excluding `.venv`, `.git`, and caches: about `0.74 MB`
- Primary space consumer: `.venv` dependency environment, especially `PySide6`

## Execution Flow

```text
DWGSort_4.0_실행.bat
  -> .venv\Scripts\python.exe cad_converter_qt.py
  -> dwgsort31.qt_app.main()
  -> MainWindow / PySide6 UI
```

Direct execution also works:

```powershell
python cad_converter_qt.py
```

## Entry Point Candidates

- Required: `cad_converter_qt.py`
- Required launcher: `DWGSort_4.0_실행.bat`
- Legacy/convenience launchers, manual review: `run.bat`, `run_and_test.bat`, `run_auto_reload.bat`

## Required Code Files

- `cad_converter_qt.py`
- `dwgsort31/__init__.py`
- `dwgsort31/config.py`
- `dwgsort31/excel_compat.py`
- `dwgsort31/excel_compat3.3.py`
- `dwgsort31/excel_compat33.py`
- `dwgsort31/extended_save.py`
- `dwgsort31/pdf_lazy.py`
- `dwgsort31/pdf_point_filter.py`
- `dwgsort31/pdf_region_dialog.py`
- `dwgsort31/pdf_vector_parser.py`
- `dwgsort31/plotting.py`
- `dwgsort31/qt_app.py`
- `dwgsort31/qt_styles.py`
- `dwgsort31/qt_widgets.py`
- `dwgsort31/qt_workers.py`
- `dwgsort31/utils.py`

`excel_compat3.3.py` is required because `excel_compat33.py` loads it dynamically with `spec_from_file_location`.

## Required Configuration Files

- None found as separate config files.
- Runtime constants live in `dwgsort31/config.py`.

## Required Resource Files

- None strictly required for current runtime.
- `videoframe_0.ico` is an application/package icon asset, but no direct runtime reference was found in code.

## Runtime File Access Found

- User-selected Excel/PDF files via Qt file dialogs.
- Output Excel/CSV files via Qt save dialogs.
- Windows font lookup: `%WINDIR%\Fonts\malgun.ttf`.
- PDF opening through PyMuPDF: `fitz.open(...)`.
- Dynamic 3.3 Excel loader: `dwgsort31/excel_compat3.3.py`.
- Legacy PDF batch loader: `Path(__file__).resolve().parents[2] / "cad_converter_gui3.0.py"`.

## Important Risk / External Dependency

`dwgsort31/pdf_lazy.py` tries to load `..\cad_converter_gui3.0.py`, which is outside this Git project root. That file is not included in the minimal copy. The current vector PDF region workflow uses in-repo modules and remains included.

If the legacy "convert selected PDF directly through worker" path must be preserved exactly, manually review and decide whether to bring that external legacy file into the project.

## Largest Folders TOP 20

| Size | Path |
|---:|---|
| 879.64 MB | `.venv` |
| 875.64 MB | `.venv\Lib` |
| 875.64 MB | `.venv\Lib\site-packages` |
| 634.07 MB | `.venv\Lib\site-packages\PySide6` |
| 101.37 MB | `.venv\Lib\site-packages\PySide6\resources` |
| 60.35 MB | `.venv\Lib\site-packages\pandas` |
| 58.77 MB | `.venv\Lib\site-packages\PySide6\translations` |
| 50.62 MB | `.venv\Lib\site-packages\pymupdf` |
| 43.65 MB | `.venv\Lib\site-packages\PySide6\translations\qtwebengine_locales` |
| 31.10 MB | `.venv\Lib\site-packages\pandas\tests` |
| 29.97 MB | `.venv\Lib\site-packages\numpy` |
| 27.23 MB | `.venv\Lib\site-packages\matplotlib` |
| 25.39 MB | `.venv\Lib\site-packages\PySide6\qml` |
| 20.02 MB | `.venv\Lib\site-packages\numpy.libs` |
| 17.78 MB | `.venv\Lib\site-packages\PySide6\plugins` |
| 15.22 MB | `.venv\Lib\site-packages\PIL` |
| 15.14 MB | `.venv\Lib\site-packages\fontTools` |
| 14.90 MB | `.venv\Lib\site-packages\PySide6\qml\QtQuick` |
| 14.45 MB | `.venv\Lib\site-packages\PySide6\metatypes` |
| 14.30 MB | `.venv\Lib\site-packages\numpy\_core` |

## Largest Files TOP 30

| Size | Path |
|---:|---|
| 195.34 MB | `.venv\Lib\site-packages\PySide6\Qt6WebEngineCore.dll` |
| 72.33 MB | `.venv\Lib\site-packages\PySide6\resources\qtwebengine_devtools_resources.debug.pak` |
| 24.46 MB | `.venv\Lib\site-packages\pymupdf\mupdfcpp64.dll` |
| 19.68 MB | `.venv\Lib\site-packages\PySide6\opengl32sw.dll` |
| 19.47 MB | `.venv\Lib\site-packages\numpy.libs\libscipy_openblas64_-63c857e738469261263c764a36be9436.dll` |
| 13.28 MB | `.venv\Lib\site-packages\PySide6\avcodec-61.dll` |
| 11.73 MB | `.venv\Lib\site-packages\pymupdf\_mupdf.pyd` |
| 11.07 MB | `.venv\Lib\site-packages\PySide6\resources\qtwebengine_devtools_resources.pak` |
| 9.99 MB | `.venv\Lib\site-packages\PySide6\Qt6Core.dll` |
| 9.98 MB | `.venv\Lib\site-packages\PySide6\resources\icudtl.dat` |
| 9.15 MB | `.venv\Lib\site-packages\PySide6\Qt6Gui.dll` |
| 8.31 MB | `.venv\Lib\site-packages\PySide6\QtOpenGL.pyd` |
| 7.53 MB | `.venv\Lib\site-packages\PIL\_avif.cp312-win_amd64.pyd` |
| 6.29 MB | `.venv\Lib\site-packages\PySide6\Qt6Widgets.dll` |
| 6.29 MB | `.venv\Lib\site-packages\PySide6\Qt6Quick.dll` |
| 5.13 MB | `.venv\Lib\site-packages\PySide6\Qt6Qml.dll` |
| 5.06 MB | `.venv\Lib\site-packages\PySide6\Qt6Designer.dll` |
| 4.63 MB | `.venv\Lib\site-packages\PySide6\QtWidgets.pyd` |
| 4.40 MB | `.venv\Lib\site-packages\PySide6\Qt6Pdf.dll` |
| 4.21 MB | `.venv\Lib\site-packages\PySide6\Qt6Quick3DRuntimeRender.dll` |
| 4.14 MB | `.venv\Lib\site-packages\PySide6\Qt6ShaderTools.dll` |
| 3.72 MB | `.venv\Lib\site-packages\PySide6\QtGui.pyd` |
| 3.63 MB | `.venv\Lib\site-packages\pymupdf\mupdf-devel\lib\mupdfcpp64.lib` |
| 3.58 MB | `.venv\Lib\site-packages\PySide6\qmlls.exe` |
| 3.54 MB | `.venv\Lib\site-packages\numpy\_core\_multiarray_umath.cp312-win_amd64.pyd` |
| 3.32 MB | `.venv\Lib\site-packages\pymupdf\__pycache__\mupdf.cpython-312.pyc` |
| 3.20 MB | `.venv\Lib\site-packages\PySide6\qml\QtQuick\Controls\FluentWinUI3\qtquickcontrols2fluentwinui3styleplugin.dll` |
| 3.18 MB | `.venv\Lib\site-packages\PySide6\QtCore.pyd` |
| 2.95 MB | `.venv\Lib\site-packages\PySide6\Qt6QuickControls2Imagine.dll` |
| 2.72 MB | `.venv\Lib\site-packages\PySide6\Qt6QuickDialogs2QuickImpl.dll` |

## A. Almost Certainly Excludable

- `__pycache__/`
- `dwgsort31/__pycache__/`
- `*.pyc`
- `.git/` for distribution/minimal copy
- `project_minimal/` if regenerating a minimal copy later

## B. Usually Excludable, Confirm If Needed

- `.venv/` because dependencies should be recreated from `requirements.txt`.
- `결과__패치전.csv`
- `결과__패치후.csv`
- `run.bat`
- `run_and_test.bat`
- `run_auto_reload.bat`
- `UI_HANDOFF_FOR_CLAUDE.md`

## C. Do Not Auto-Delete

- `cad_converter_qt.py`
- `DWGSort_4.0_실행.bat`
- `README.md`
- `dwgsort31/` required modules listed above
- `dwgsort31/excel_compat3.3.py` because it is dynamically loaded

## D. Hold / Manual Review

- `dwgsort31/excel_compat__1.py`
- `dwgsort31/excel_compat__2.py`
- `videoframe_0.ico`
- `3.3은 점찍기 로직개선.txt`
- External legacy dependency: `..\cad_converter_gui3.0.py`

## Dangerous Deletion Candidates

- `dwgsort31/pdf_lazy.py`: appears legacy, but is imported by `qt_workers.py`.
- `dwgsort31/excel_compat3.3.py`: filename looks odd, but is dynamically imported.
- `dwgsort31/plotting.py`: imported lazily inside preview methods.

## Expected Space Savings

- Excluding `.venv`: about `879.64 MB`.
- Excluding `.git` and bytecode caches: about `0.13 MB` plus cache files.
- Excluding sample result CSVs and handoff notes: about `20 KB`.
- Minimal source copy is expected to be under `1 MB` before dependencies are installed.

## Minimal Project Plan

Include:

- Runtime Python source files listed in Required Code Files.
- `DWGSort_4.0_실행.bat`.
- `README.md`.
- Generated `requirements.txt`.
- Generated `README_MINIMAL.md`.
- Analysis scripts and this cleanup report.

Exclude:

- `.venv/`
- `.git/`
- `__pycache__/`
- generated CSV samples
- backup Excel modules `excel_compat__1.py`, `excel_compat__2.py`
- legacy helper launchers unless manually needed
- icon asset unless packaging requires it

## Minimal Test Commands

```powershell
cd E:\ai\pythonpythonpython\dwgsort\dwgsort\project_minimal
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python cad_converter_qt.py
```

Or:

```powershell
cd E:\ai\pythonpythonpython\dwgsort\dwgsort\project_minimal
.\DWGSort_4.0_실행.bat
```
