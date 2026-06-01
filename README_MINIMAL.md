# DWGSort Minimal Quick Notes

자세한 설명은 `README.md`를 보세요. 이 파일은 최소 실행본에서 바로 필요한 요약입니다.

## 실행

```powershell
cd E:\ai\pythonpythonpython\dwgsort\dwgsort\project_minimal
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python cad_converter_qt.py
```

또는:

```powershell
.\DWGSort_4.0_실행.bat
```

## 핵심

- Excel/XLS: `Contents`, `Position` 기반으로 `누가거리`, `관저고` 추출
- PDF: CAD 벡터 PDF의 선택 영역에서 텍스트 좌표 추출
- 처음 미리보기: 전체 점
- `적용`: 현재 설정으로 점 정리
- `초기화`: 설정값은 그대로 두고 전체 점으로 복귀
- PDF 점 정리: 변환 설정의 `Y오차`를 사용하지 않음

## 주의

- 스캔 PDF/OCR은 지원하지 않습니다.
- `videoframe_0.ico`, legacy run scripts, backup Excel modules는 최소 실행에 필요 없어 제외했습니다.
- `dwgsort31/pdf_lazy.py`의 legacy PDF 직접 처리 경로는 `..\cad_converter_gui3.0.py`를 찾습니다. 이 외부 파일은 최소본에 포함하지 않았습니다.
