from pathlib import Path
import importlib.util


def process_pdf_with_30(file_path, log_func, tolerance, pdf_start_page=None, pdf_end_page=None):
    """Load the old 3.0 PDF extractor only when a PDF is actually processed."""
    legacy_path = Path(__file__).resolve().parents[2] / "cad_converter_gui3.0.py"
    if not legacy_path.exists():
        log_func(" ❌ PDF 처리 모듈을 찾을 수 없습니다.")
        return None

    spec = importlib.util.spec_from_file_location("dwgsort_legacy_30", legacy_path)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    return legacy.process_pdf_data(
        file_path, log_func, tolerance, pdf_start_page, pdf_end_page
    )
