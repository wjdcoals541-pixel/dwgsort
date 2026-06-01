# DWGSort 4.0 Minimal

DWGSort 4.0은 CAD에서 추출한 Excel/XLS 데이터 또는 CAD에서 내보낸 벡터 PDF에서 종단면도용 `누가거리`와 `관저고` 값을 추출하고, 그래프 미리보기와 CSV/Excel 저장을 제공하는 Windows 데스크톱 프로그램입니다.

이 폴더는 원본 프로젝트에서 실행에 필요한 최소 파일만 복사한 `project_minimal` 버전입니다. Git 히스토리, 가상환경, 캐시, 샘플 결과 CSV, 백업 모듈은 포함하지 않습니다.

## 실행 방법

권장 실행:

```powershell
cd E:\ai\pythonpythonpython\dwgsort\dwgsort\project_minimal
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python cad_converter_qt.py
```

배치 파일 실행:

```powershell
cd E:\ai\pythonpythonpython\dwgsort\dwgsort\project_minimal
.\DWGSort_4.0_실행.bat
```

`DWGSort_4.0_실행.bat`는 현재 폴더의 `.venv\Scripts\python.exe`가 있으면 그것을 사용하고, 없으면 시스템 `python`으로 `cad_converter_qt.py`를 실행합니다.

## 필요한 패키지

`requirements.txt`:

- `PySide6`: GUI
- `pandas`: Excel/PDF 추출 결과 데이터 처리
- `matplotlib`: 그래프 미리보기
- `openpyxl`: `.xlsx` 저장
- `xlrd`: `.xls` 읽기
- `PyMuPDF`: 벡터 PDF 렌더링과 텍스트 추출

## 프로그램 목적

- DWG `DATAEXTRACTION` 등에서 나온 Excel 형식의 `Contents`, `Position` 데이터를 읽습니다.
- CAD에서 내보낸 벡터 PDF의 선택 영역에서 텍스트 좌표를 추출합니다.
- `누가거리`와 `관저고` 행을 찾아 거리-고도 쌍으로 매칭합니다.
- 처음에는 가능한 전체 점을 보여주고, 사용자가 원할 때만 변환 설정을 적용해 점을 정리합니다.
- 결과를 표, 그래프, Excel, CSV로 확인하거나 저장합니다.

## 지원 파일

- Excel: `.xls`, `.xlsx`
- PDF: CAD에서 내보낸 벡터 PDF

지원하지 않는 것:

- 스캔 PDF
- OCR
- 이미지 기반 도면 판독
- PDF 좌표 프리셋 저장
- 추출 결과 수동 편집
- 그래프 이미지 저장
- Excel 내부 차트 삽입
- Excel과 PDF를 한 번의 처리 작업에서 섞는 방식

## 기본 실행 흐름

```text
DWGSort_4.0_실행.bat
  -> cad_converter_qt.py
  -> dwgsort31.qt_app.main()
  -> MainWindow
```

직접 실행도 가능합니다.

```powershell
python cad_converter_qt.py
```

## Excel 처리 방식

1. 사용자가 `.xls` 또는 `.xlsx` 파일을 선택합니다.
2. `pandas.read_excel(..., sheet_name=None)`로 모든 시트를 읽어 합칩니다.
3. `Contents`, `Position` 컬럼을 찾습니다.
4. `Position`에서 X, Y 좌표를 파싱합니다.
5. `누가거리`, `관저고` 라벨 행을 찾습니다.
6. 변환 설정의 `Y오차`로 같은 행에 있는 숫자 후보를 찾습니다.
7. X 좌표가 가까운 거리/고도 값을 매칭합니다.
8. 처음 미리보기는 전체 점을 보여줍니다.
9. `적용` 버튼을 누르면 기울기, 거리, 고점 설정으로 점 정리를 적용합니다.
10. `초기화` 버튼을 누르면 설정값은 그대로 두고 미리보기/결과표만 전체 점으로 되돌립니다.

Excel에서 `Y오차`는 원본 점 추출에 사용됩니다.

## PDF 처리 방식

PDF는 두 흐름이 있습니다.

### 권장 흐름: PDF 영역 지정

1. 사용자가 PDF 파일을 선택합니다.
2. `PDF 영역 지정` 버튼을 누릅니다.
3. PDF 미리보기 창에서 표/데이터 영역을 선택합니다.
4. 선택 영역은 자동으로 약간 확장되어 라벨 주변 텍스트까지 잡습니다.
5. PyMuPDF가 벡터 텍스트와 좌표를 추출합니다.
6. PDF 전용 설정값으로 라벨 행과 숫자 행을 찾습니다.
7. `누가거리`, `관저고` 값을 X 좌표 기준으로 매칭합니다.
8. 거리 값이 크게 되돌아가면 `line_id`를 나누어 여러 종단 라인을 표현합니다.
9. 처음 미리보기는 전체 점을 보여줍니다.
10. `적용` 버튼을 누르면 PDF 전용 점 정리를 적용합니다.
11. `초기화` 버튼을 누르면 설정값은 그대로 두고 전체 점으로 되돌립니다.

PDF 점 정리는 변환 설정의 `Y오차`를 사용하지 않습니다. PDF 점 정리는 `기울기`, `거리`, `고점`, 최소 간격 1.0m 기준만 사용합니다.

### Legacy 흐름: 직접 PDF 변환 시작

`dwgsort31/qt_workers.py`는 PDF 파일을 직접 `변환 시작`으로 처리할 때 `dwgsort31/pdf_lazy.py`의 `process_pdf_with_30()`을 호출할 수 있습니다.

주의:

- `pdf_lazy.py`는 `..\cad_converter_gui3.0.py`를 찾습니다.
- 이 파일은 `project_minimal`에 포함되어 있지 않습니다.
- 현재 권장 벡터 PDF 영역 지정 흐름은 `pdf_region_dialog.py`, `pdf_vector_parser.py` 안에 포함되어 있으므로 동작합니다.
- legacy 직접 PDF 변환까지 반드시 살려야 한다면 외부 `cad_converter_gui3.0.py`를 수동 검토해야 합니다.

## PDF 영역 지정 창 기능

구현 파일: `dwgsort31/pdf_region_dialog.py`

주요 기능:

- 드래그 선택
- 두 점 선택
- 두 점 선택 중 첫 점 기준 미리보기 사각형
- `Esc`: 두 점 선택의 첫 점 취소
- 마우스 휠 줌
- 우클릭 드래그 팬
- `Space + 좌클릭 드래그` 팬
- 방향키로 선택 박스 이동
- `Shift + 방향키`: 10px 단위 이동
- `Ctrl + 방향키`: 선택 박스 크기 조절
- 전체 보기, 가로폭 맞춤, 100%, 200%, 400%, 800% 줌
- 영역 검사로 추출 텍스트, 행 후보, 매칭 상태 확인
- 선택 영역, 실제 추출 영역, 선택/제외된 행, X 매칭 선 오버레이 표시

PDF 전용 설정:

- `PDF_Y_TOLERANCE = 5.0`
- `PDF_X_TOLERANCE = 10.0`
- `PDF_ROW_CLUSTER_TOLERANCE = 1.5`
- `PDF_REGION_PAD_RATIO = 0.15`

## 변환 설정

UI 위치: `변환 설정`

- `저장`: `2.4`, `3.1`, `3.3`
- `Y오차`: Excel 원본 점 추출용
- `기울기`: 점 정리 시 기울기 변화 민감도
- `거리`: 중요한 점 사이가 너무 멀 때 보조 점을 남기는 최대 거리
- `고점`: 봉우리/골짜기 판정 민감도
- `PDF`: PDF 시작/끝 페이지
- `적용`: 현재 설정으로 점 정리 적용
- `초기화`: 설정값은 바꾸지 않고 미리보기와 결과표만 전체 점으로 복귀

설정값을 바꿔도 자동으로 필터가 적용되지 않습니다. 점 정리는 `적용`을 눌렀을 때만 반영됩니다.

## 그래프와 결과표

- 왼쪽 그래프 미리보기는 현재 결과표와 같은 데이터를 그립니다.
- 처음 파일을 불러오면 전체 점이 표시됩니다.
- `적용` 후에는 정리된 점이 표시됩니다.
- `초기화` 후에는 전체 점이 다시 표시됩니다.
- PDF 결과표는 디버그용 컬럼을 포함할 수 있습니다.
- 저장되는 CSV/Excel 기본 결과는 단순한 `관저고`, `누가거리`, `결과` 형태입니다.

## 복사 기능

- `변환 결과 미리보기` 제목 오른쪽의 `복사`: 현재 결과의 관저고/누가거리 컬럼을 클립보드에 복사합니다.
- 표에서 `Ctrl+C`: 선택한 셀 범위를 클립보드에 복사합니다.
- `실행 로그`의 `로그 복사`: 로그 전체를 클립보드에 복사합니다.

## 저장 기능

- `엑셀로 저장`: 현재 결과를 `.xlsx`로 저장합니다.
- `CSV로 저장`: 현재 결과를 UTF-8 BOM 포함 CSV로 저장합니다.
- `변환 시작`: 선택 파일을 백그라운드 worker로 처리하고, 파일 위치에 `결과_<원본파일명>.xlsx`를 생성합니다.
- 이미 저장된 결과가 있으면 같은 경로를 다시 안내합니다.
- 파일명 충돌 시 `safe_output_path()`가 `_1`, `_2` 같은 번호를 붙입니다.

## 로그와 상태 표시

- PDF 추출과 매칭은 실패 원인을 찾기 위해 비교적 자세한 로그를 남깁니다.
- 로그에는 선택 영역, 실제 추출 영역, 행 후보, X 매칭, line_id 감지 등이 표시됩니다.
- 진행 상황 카드에는 진행률, 예상 남은 시간, 현재 파일명이 표시됩니다.

## 포함된 파일

```text
project_minimal/
  cad_converter_qt.py
  DWGSort_4.0_실행.bat
  README.md
  README_MINIMAL.md
  requirements.txt
  cleanup_candidates.md
  analyze_project_size.py
  create_minimal_project.py
  dwgsort31/
    __init__.py
    config.py
    excel_compat.py
    excel_compat3.3.py
    excel_compat33.py
    extended_save.py
    pdf_lazy.py
    pdf_point_filter.py
    pdf_region_dialog.py
    pdf_vector_parser.py
    plotting.py
    qt_app.py
    qt_styles.py
    qt_widgets.py
    qt_workers.py
    utils.py
```

## 포함하지 않은 파일과 이유

- `.venv/`: `requirements.txt`로 재생성합니다.
- `.git/`: 최소 실행본에는 Git 히스토리가 필요 없습니다.
- `__pycache__/`, `*.pyc`: 실행 중 자동 생성되는 캐시입니다.
- `videoframe_0.ico`: 현재 코드에서 `QIcon`, `setWindowIcon`, 파일명 참조가 없습니다.
- `run.bat`, `run_and_test.bat`, `run_auto_reload.bat`: legacy 실행 도우미이며 필수 실행 경로가 아닙니다.
- `dwgsort31/excel_compat__1.py`, `dwgsort31/excel_compat__2.py`: 백업 모듈이며 실제 import가 확인되지 않았습니다.
- 샘플 결과 CSV: 실행 필수 데이터가 아닙니다.
- `UI_HANDOFF_FOR_CLAUDE.md`: 개발 인수인계 문서이며 실행 필수 파일이 아닙니다.

## 반드시 유지해야 하는 특이 파일

- `dwgsort31/excel_compat3.3.py`: 파일명에 점이 들어 있어 일반 import는 어렵지만, `excel_compat33.py`가 `spec_from_file_location()`으로 동적 로딩합니다.
- `dwgsort31/pdf_lazy.py`: legacy PDF 직접 변환 경로 때문에 `qt_workers.py`에서 import합니다.
- `dwgsort31/plotting.py`: 그래프 새 창 미리보기에서 함수 내부 lazy import로 사용합니다.

## 검증된 내용

`project_minimal` 기준으로 확인한 항목:

- `.venv` 생성과 패키지 설치 가능
- `requirements.txt` 설치 성공
- 모든 Python 파일 `py_compile` 성공
- 내부 모듈 import 성공
- `excel_compat3.3.py` 동적 로딩 성공
- PySide6 `MainWindow` 생성 성공
- `DWGSort_4.0_실행.bat`가 `project_minimal\.venv\Scripts\python.exe cad_converter_qt.py`를 호출하는 것 확인
- 창 제목: `CAD PDF Converter Pro - DWG Sort 4.0`

## 유지보수 가이드

- UI 버튼, 카드, 미리보기, 저장 흐름 수정: `dwgsort31/qt_app.py`
- PDF 선택 창, 줌/팬/오버레이 수정: `dwgsort31/pdf_region_dialog.py`
- PDF 텍스트 추출, 라벨/행 선택, X 매칭 수정: `dwgsort31/pdf_vector_parser.py`
- PDF 점 정리 수정: `dwgsort31/pdf_point_filter.py`
- Excel 원본 추출과 2.4 저장 수정: `dwgsort31/excel_compat.py`
- 3.3 점 정리 수정: `dwgsort31/excel_compat3.3.py`
- 3.3 동적 로더 수정: `dwgsort31/excel_compat33.py`
- 백그라운드 변환과 저장 worker 수정: `dwgsort31/qt_workers.py`
- 스타일 수정: `dwgsort31/qt_styles.py`
- 공용 위젯 수정: `dwgsort31/qt_widgets.py`

Excel 호환 로직은 오래된 흐름을 보존하는 목적이 크므로, PDF 전용 변경 중에는 가능한 건드리지 않는 것이 좋습니다.

## 문제 해결

`ModuleNotFoundError: No module named 'PySide6'`:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

PDF 미리보기가 열리지 않는 경우:

- `PyMuPDF` 설치 여부를 확인합니다.
- 스캔 PDF가 아닌 CAD 벡터 PDF인지 확인합니다.

PDF 결과가 비어 있는 경우:

- 선택 영역이 실제 데이터 행과 라벨을 포함하는지 확인합니다.
- PDF 영역 지정 창의 영역 검사와 로그 복사를 사용해 추출 텍스트를 확인합니다.
- PDF 전용 `Y/X/행 클러스터` 설정을 조정합니다.

Excel 결과가 비어 있는 경우:

- 파일에 `Contents`, `Position` 컬럼이 있는지 확인합니다.
- `누가거리`, `관저고` 라벨이 추출 데이터에 존재하는지 확인합니다.
- `Y오차` 값을 조정합니다.

Legacy PDF 직접 변환에서 `PDF 처리 모듈을 찾을 수 없습니다.`가 나오는 경우:

- `..\cad_converter_gui3.0.py`가 없는 것이 원인입니다.
- 권장 PDF 영역 지정 흐름을 사용하거나, legacy 파일을 별도로 검토해 포함해야 합니다.
