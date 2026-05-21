"""Loader for the 3.3 Excel compatibility logic.

The source file is named ``excel_compat3.3.py`` for version clarity, but the
dot in that filename prevents normal package imports.  This module keeps the
3.3 implementation isolated while exposing import-friendly callables.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_SOURCE_PATH = Path(__file__).with_name("excel_compat3.3.py")
_SPEC = spec_from_file_location("dwgsort31.excel_compat3_3_source", _SOURCE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load 3.3 compatibility module: {_SOURCE_PATH}")

_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

filter_graph_points_33 = _MODULE.filter_graph_points_24
save_compat_33_excel = _MODULE.save_compat_24_excel
