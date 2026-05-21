# DWGSort

DWGSort is a Python/PySide desktop tool for extracting profile data from CAD-related files and drawing/saving distance-elevation results.

Current main branch target: **DWG Sort 4.0**.

4.0 keeps the existing 3.3 Excel/XLS workflow intact and adds support for **vector PDFs exported from CAD**. Scanned PDFs and OCR are intentionally not supported in 4.0.

## Quick Start

```bat
DWGSort_4.0_실행.bat
```

Alternative legacy run scripts are also kept:

```bat
run.bat
run_and_test.bat
run_auto_reload.bat
```

Main Python entry point:

```bash
python cad_converter_qt.py
```

## What 4.0 Does

### Existing Excel Flow

The original XLS flow is preserved:

1. User selects XLS files extracted from DWG `DATAEXTRACTION`.
2. The app reads Excel-like `Contents` and `Position` data.
3. It finds the Korean labels `누가거리` and `관저고`.
4. It collects numbers near each label row by Y coordinate.
5. It matches distance/elevation values by nearby X coordinate.
6. It previews the graph.
7. It saves result data to CSV/Excel.

Current graph behavior:

- Graphs are shown inside the program or in a matplotlib preview window.
- Graph images are not saved.
- Graphs are not inserted into Excel files.
- CSV/Excel export stores result data, not graph images.

### New Vector PDF Flow

4.0 adds vector PDF processing for CAD-exported PDFs only:

1. User selects a PDF file.
2. User clicks `PDF 영역 지정`.
3. The PDF preview dialog opens.
4. User chooses the data area by drag selection or two-point selection.
5. The app expands the selected area before extraction.
6. PyMuPDF extracts vector text objects inside the expanded area.
7. Extracted PDF text is converted into an Excel-like internal structure:

```json
{
  "page": 1,
  "contents": "10.00",
  "x": 240.10,
  "y": 340.40,
  "bbox": [230.0, 335.0, 250.0, 345.0],
  "rotation": 0
}
```

8. The app finds `누가거리` and `관저고` labels.
9. It clusters numeric text by Y coordinate into rows.
10. It selects the true distance row and true elevation row.
11. It matches values by X coordinate.
12. It splits multiple profile lines with `line_id` when distance drops sharply.
13. It shows a read-only result table.
14. It uses the existing graph preview and CSV/Excel result save flow.

## Important 4.0 Limits

Do not add these to 4.0 unless the product direction changes:

- No OCR.
- No scanned PDF support.
- No PDF coordinate preset saving.
- No manual editing of extracted result values.
- No graph image saving.
- No Excel embedded chart insertion.
- Do not mix Excel and PDF in one processing run.
- Do not change the existing Excel/XLS logic unless fixing a proven regression.

## PDF Region Selection UI

Implemented in `dwgsort31/pdf_region_dialog.py`.

Supported controls:

- Drag selection.
- Two-point selection.
- First point preview rectangle while moving the mouse.
- Esc cancels the first point in two-point mode.
- Mouse wheel zoom.
- Right-drag pan.
- Space + left-drag pan.
- Arrow keys move the selected box.
- Shift + arrow moves by 10 px.
- Ctrl + arrow resizes the selected box.
- Zoom buttons: `전체 보기`, `가로폭 맞춤`, `100%`, `200%`, `400%`, `800%`.
- `영역 검사` previews extraction and row detection before applying.

Overlay legend:

- Blue solid box: user-selected original region.
- Sky-blue dashed/transparent box: actual extraction region after automatic expansion.
- Yellow horizontal band: selected `누가거리` row.
- Green horizontal band: selected `관저고` row.
- Gray/red faint bands: excluded candidate rows such as `구간거리`, `지반고`, or `토피`.
- Optional X-match lines are shown only when `X매칭 보기` is enabled.

The sky-blue extraction box is intentionally larger than the selected box. It uses about 15% padding so the user can select the numeric table area roughly while still capturing labels that sit slightly to the left or nearby.

## PDF Detection Settings

Defined in `dwgsort31/config.py`:

```python
PDF_Y_TOLERANCE = 5.0
PDF_X_TOLERANCE = 10.0
PDF_ROW_CLUSTER_TOLERANCE = 1.5
PDF_REGION_PAD_RATIO = 0.15
```

Meaning:

- `PDF_Y_TOLERANCE`: how far from a label Y coordinate candidate numeric rows may be.
- `PDF_X_TOLERANCE`: max X distance for distance/elevation matching.
- `PDF_ROW_CLUSTER_TOLERANCE`: how tightly numeric text is grouped into the same row.
- `PDF_REGION_PAD_RATIO`: automatic extraction padding based on selected region size.

These PDF values are separate from Excel settings.

## PDF Row Selection Logic

Implemented mainly in `dwgsort31/pdf_vector_parser.py`.

The parser does not simply take every number near the label Y coordinate. That caused bugs when CAD PDFs extracted labels like:

- `구간거리누가거리`
- `지반고관저고토피`

Instead it now:

1. Extracts all numeric text inside the actual extraction region.
2. Clusters numbers into Y rows.
3. Finds candidate rows near the labels.
4. Scores `누가거리` rows by monotonic increase, value range, and count.
5. Picks the true cumulative distance row.
6. Picks the `관저고` row, preferring the middle row when `지반고/관저고/토피` are all present.
7. Logs selected and excluded rows with reasons.

This prevents `구간거리` values from being mixed into `누가거리`, and prevents `지반고` or `토피` from being used as `관저고`.

## Result Data

PDF result preview table columns:

- `line_id`
- `페이지`
- `누가거리`
- `관저고`
- `누가거리 X`
- `관저고 X`
- `원본 누가거리`
- `원본 관저고`
- `상태`

Default CSV/Excel export stays simple:

- `관저고`
- `누가거리`
- `결과`

Debug columns are shown in the UI where useful, but they are not mixed into the default saved result format.

## Folder Structure

```text
.
+-- DWGSort_4.0_실행.bat       # One-click Windows launcher for 4.0
+-- README.md                  # Project and AI handoff documentation
+-- cad_converter_qt.py        # Main Qt application entry point
+-- run.bat                    # Legacy basic Windows run script
+-- run_and_test.bat           # Legacy run/check helper
+-- run_auto_reload.bat        # Legacy auto-reload run helper
+-- videoframe_0.ico           # Application icon
+-- UI_HANDOFF_FOR_CLAUDE.md   # Previous UI handoff notes
+-- 결과__패치전.csv             # Sample/result data before patch
+-- 결과__패치후.csv             # Sample/result data after patch
+-- 3.3은 점찍기 로직개선.txt      # Note for the 3.3 point-logic change
+-- dwgsort31/
    +-- __init__.py            # Package marker
    +-- config.py              # Shared config and PDF tolerance constants
    +-- excel_compat.py        # Excel compatibility, parsing, and result save helpers
    +-- excel_compat3.3.py     # 3.3 Excel compatibility/reference module
    +-- excel_compat33.py      # 3.3 helper/backup module
    +-- excel_compat__1.py     # Older Excel compatibility backup
    +-- excel_compat__2.py     # Older Excel compatibility backup
    +-- extended_save.py       # Extended save/export helpers
    +-- pdf_lazy.py            # Lazy PDF loading helpers
    +-- pdf_region_dialog.py   # PDF preview, selection, zoom, pan, overlays, inspection UI
    +-- pdf_vector_parser.py   # Vector PDF text extraction, row detection, X matching, validation
    +-- plotting.py            # Matplotlib plotting helpers, including line_id split support
    +-- qt_app.py              # Main application window and Excel/PDF workflow orchestration
    +-- qt_styles.py           # Qt stylesheet definitions
    +-- qt_widgets.py          # Custom Qt widgets
    +-- qt_workers.py          # Background worker logic
    +-- utils.py               # Shared utility functions
```

## File Responsibilities For AI Maintainers

Start here:

- `cad_converter_qt.py`: launches the Qt app.
- `dwgsort31/qt_app.py`: main window, button wiring, result table, graph preview, save flow.
- `dwgsort31/pdf_region_dialog.py`: PDF preview dialog and region selection UX.
- `dwgsort31/pdf_vector_parser.py`: all vector PDF extraction and PDF-specific detection logic.
- `dwgsort31/config.py`: PDF tolerance/padding constants and other shared configuration.
- `dwgsort31/plotting.py`: graph rendering helpers; supports splitting PDF lines by `line_id`.
- `dwgsort31/excel_compat.py`: existing Excel parsing/saving compatibility logic.

When changing PDF behavior, prefer editing `pdf_vector_parser.py` and `pdf_region_dialog.py`.

When changing UI orchestration, edit `qt_app.py`.

When changing graph drawing, check both `plotting.py` and graph-related methods in `qt_app.py`.

Avoid touching Excel compatibility files for PDF-only changes.

## Debug Logging

PDF logs are intentionally verbose because CAD PDF extraction can fail for layout reasons.

Useful log patterns:

```text
[PDF] 사용자 선택 영역: ...
[PDF] 실제 추출 영역: ...
[PDF] PDF 설정: y_tolerance=..., x_tolerance=..., row_cluster_tolerance=...
[PDF] 감지된 숫자 행 클러스터: ...
[PDF] 누가거리 라벨 인식: contents='...'
[PDF] 관저고 라벨 인식: contents='...'
[PDF][DEBUG] 누가거리 후보 행: ...
[PDF][DEBUG] 관저고 후보 행: ...
[PDF] X좌표 매칭 성공: ...
[PDF] line_id 감지: ...
```

The UI has a log copy button so users can paste logs into an AI assistant for debugging.

## Version History

Saved Git tags:

```bash
git checkout v3.1
git checkout v3.2
git checkout v3.3
git checkout v4.0
```

Main branch after `v4.0` includes additional PDF region selection and inspection improvements.

Return to the current branch:

```bash
git checkout main
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
