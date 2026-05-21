# UI 인수인계 - DWG Sort 3.3

이 문서는 Claude에게 UI 관련 작업을 넘기기 위한 빠른 진입점입니다. 작업 대상은 독립 복사본인 `E:\ai\pythonpythonpython\dwgsort\3.3` 폴더입니다. `3.2` 폴더는 건드리지 마세요.

## 프로젝트 실행/진입 파일

- 앱 실행 진입점: `E:\ai\pythonpythonpython\dwgsort\3.3\cad_converter_qt.py`
- 메인 UI 파일: `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\qt_app.py`
- 공용 UI 위젯: `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\qt_widgets.py`
- 스타일시트/테마: `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\qt_styles.py`

## UI 핵심 위치

### `qt_app.py`

- `MainWindow` 클래스 시작: `dwgsort31\qt_app.py:61`
- 창 제목/기본 크기: `dwgsort31\qt_app.py:65`
- 전체 화면 구성: `dwgsort31\qt_app.py:97`
- 파일 선택 카드: `dwgsort31\qt_app.py:133`
- 변환 설정 카드: `dwgsort31\qt_app.py:165`
- 저장 방식 콤보박스: `dwgsort31\qt_app.py:173`
- 저장 기본값 `3.3`: `dwgsort31\qt_app.py:175`
- `고점기준` 입력칸 `peak_prominence_spin`: `dwgsort31\qt_app.py:196`
- 설정 필드 배열: `dwgsort31\qt_app.py:222`
- 실행/초기화/저장 버튼: `dwgsort31\qt_app.py:272`
- 결과 테이블/복사 버튼: `dwgsort31\qt_app.py:302`
- 팝업 그래프 미리보기: `dwgsort31\qt_app.py:387`
- 인라인 미리보기 갱신: `dwgsort31\qt_app.py:422`
- 인라인 그래프 그리기: `dwgsort31\qt_app.py:509`
- 변환 시작 및 worker settings 생성: `dwgsort31\qt_app.py:584`
- 저장모드 판별: `dwgsort31\qt_app.py:740`
- 저장모드별 필터 함수 선택: `dwgsort31\qt_app.py:748`
- 반응형 레이아웃 조정: `dwgsort31\qt_app.py:782`
- 커스텀 타이틀바: `dwgsort31\qt_app.py:879`
- 앱 생성 및 테마 적용: `dwgsort31\qt_app.py:960`

### `qt_widgets.py`

- 버튼 팩토리 `make_button`: `dwgsort31\qt_widgets.py:14`
- 카드 컨테이너 `Card`: `dwgsort31\qt_widgets.py:23`
- 드래그 앤 드롭 파일 영역 `DropZone`: `dwgsort31\qt_widgets.py:72`

### `qt_styles.py`

- 전체 QSS 테마 적용 함수 `apply_fluent_theme`: `dwgsort31\qt_styles.py:181`

## 현재 3.3 UI 상태

- 저장 방식 콤보는 `["2.4", "3.1", "3.3"]`입니다.
- 기본 선택값은 `3.3`입니다.
- `고점기준` 입력칸이 추가되어 있습니다.
  - 변수명: `self.peak_prominence_spin`
  - 타입: `QDoubleSpinBox`
  - 범위: `0.0 ~ 10.0`
  - step: `0.05`
  - 기본값: `0.30`
  - 값 변경 시 `update_inline_preview` 호출
- `고점기준` 값은 미리보기와 실제 변환 모두에 전달됩니다.

## UI와 로직 연결 흐름

1. 사용자가 `qt_app.py:173`의 저장 콤보에서 `3.3`을 선택합니다.
2. `current_save_mode()`가 `SAVE_MODE_COMPAT_33`을 반환합니다.
3. 미리보기에서는 `current_filter_func()`가 3.3 필터를 선택합니다.
4. 변환 시작 시 `start_analysis()`가 settings 딕셔너리에 `peak_prominence`를 넣습니다.
5. `qt_workers.py`의 `AnalysisWorker`가 settings를 받아 실제 저장/필터링을 실행합니다.

관련 로직 파일:

- 설정 상수: `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\config.py`
- 백그라운드 변환 worker: `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\qt_workers.py`
- 3.3 로직 로더: `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\excel_compat33.py`
- 실제 3.3 점찍기/저장 로직: `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\excel_compat3.3.py`

## 주의사항

- `excel_compat3.3.py`는 파일명에 점이 들어가서 Python 일반 import가 안 됩니다.
- 그래서 `excel_compat33.py`가 `importlib`로 로드합니다. 이 파일을 지우거나 우회하지 마세요.
- UI 작업 시 `qt_app.py`를 중심으로 수정하고, 반복되는 버튼/카드 스타일은 `qt_widgets.py`, 색상과 QSS는 `qt_styles.py`에서 수정하세요.
- 2.4 / 3.1 저장 흐름은 유지해야 합니다.
- 3.3 선택 시에만 3.3 필터와 저장 로직이 실행되어야 합니다.
- `peak_prominence`는 기존 `slope`, `max_dist`와 별개 값입니다. UI 배치 변경 시 settings 전달은 유지하세요.

## 최근 변경 파일

- `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\config.py`
- `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\qt_app.py`
- `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\qt_workers.py`
- `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\excel_compat.py`
- `E:\ai\pythonpythonpython\dwgsort\3.3\dwgsort31\excel_compat33.py`

## 검증 참고

이전 변경 직후 아래 문법 검사는 통과했습니다.

```powershell
.\.venv\Scripts\python.exe -m py_compile .\dwgsort31\config.py .\dwgsort31\excel_compat.py .\dwgsort31\excel_compat33.py .\dwgsort31\excel_compat3.3.py .\dwgsort31\qt_app.py .\dwgsort31\qt_workers.py
```
