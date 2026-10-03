"""Fill the supplied pipeline template without round-tripping its native objects.

Only affected OOXML parts are edited. Styles, drawings, printer binaries and
unrelated sheets remain byte-for-byte identical to the selected template.
"""
from io import BytesIO
from pathlib import Path
import math
import re
from xml.dom import minidom as DOM
from zipfile import ZipFile

import pandas as pd

from .excel_compat import process_excel_data
from .air_valves import merge_valves


def read_bytes(path):
    """Allow Windows Excel's read-sharing handle while never writing the source."""
    try:
        return Path(path).read_bytes()
    except PermissionError:
        import os
        if os.name != 'nt':
            raise
        import ctypes
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        handle = create(str(Path(path).resolve()), 0x80000000, 7, None, 3, 0, None)
        if handle == wintypes.HANDLE(-1).value:
            raise PermissionError('파일을 읽을 수 없습니다. Excel에서 저장하고 닫아주세요: ' + str(path))
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        with os.fdopen(fd, 'rb') as stream:
            return stream.read()


def read_profiles(path, log=lambda _: None):
    data = read_bytes(path)
    engine = 'xlrd' if Path(path).suffix.lower() == '.xls' else 'openpyxl'
    sheets = pd.read_excel(BytesIO(data), sheet_name=None, engine=engine)
    found = []
    for name, frame in sheets.items():
        names = {re.sub(r'\s+', '', str(c)): c for c in frame.columns}
        distance = next((names[c] for c in ('누가거리', '추가거리', '누적거리') if c in names), None)
        if distance is None or '관저고' not in names:
            continue
        frame = frame.rename(columns={distance: '누가거리', names['관저고']: '관저고'})
        if 'line_id' in frame:
            if frame['line_id'].isna().any():
                raise ValueError('line_id가 비어 있는 행이 있습니다.')
            groups = frame.groupby('line_id', sort=False)
        else:
            groups = [(None, frame)]
        for key, group in groups:
            suffix = f'{name}_{key}' if key is not None else name
            found.append((suffix, normalize_points(group)))
    if found:
        log('결과 표의 모든 점을 그대로 사용합니다. 추가 점 정리는 하지 않습니다.')
        return found
    # The CAD parser reads a path; a private temporary copy also handles Excel locks.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=Path(path).suffix, delete=False) as stream:
        stream.write(data)
        temporary_path = Path(stream.name)
    try:
        frame = process_excel_data(str(temporary_path), log, 5.0)
    finally:
        temporary_path.unlink(missing_ok=True)
    if frame is None or frame.empty:
        raise ValueError('누가거리/추가거리와 관저고를 읽지 못했습니다.')
    groups = frame.groupby('line_id', sort=False) if 'line_id' in frame else [(1, frame)]
    return [(f'종단{key}', normalize_points(group)) for key, group in groups]


def normalize_points(frame):
    points = []
    for row, (distance, elevation) in enumerate(zip(frame['누가거리'], frame['관저고']), 2):
        try:
            distance, elevation = (float(str(v).replace(',', '').strip()) for v in (distance, elevation))
        except (TypeError, ValueError):
            raise ValueError(f'{row}행의 거리 또는 관저고가 숫자가 아닙니다.') from None
        if not all(math.isfinite(v) for v in (distance, elevation)) or distance < 0:
            raise ValueError(f'{row}행의 거리 또는 관저고가 유효하지 않습니다.')
        if points and distance < points[-1][0]:
            raise ValueError('누가거리가 감소합니다. 서로 다른 종단은 line_id로 구분해주세요.')
        points.append((distance, elevation))
    if not points:
        raise ValueError('입력 데이터가 없습니다.')
    return points


def elements(node, tag):
    return list(node.getElementsByTagName(tag))


def child(doc, parent, tag, text=None, **attrs):
    node = doc.createElement(tag)
    for key, val in attrs.items():
        node.setAttribute(key, str(val))
    if text is not None:
        node.appendChild(doc.createTextNode(str(text)))
    parent.appendChild(node)
    return node


def clear(node):
    for item in list(node.childNodes):
        node.removeChild(item)


def write_cell(doc, row, col, value=None, formula=None):
    address = f'{col}{row.getAttribute("r")}'
    cell = next((c for c in elements(row, 'c') if c.getAttribute('r') == address), None)
    if cell is None:
        cell = child(doc, row, 'c', r=address)
    clear(cell)
    if cell.hasAttribute('t'):
        cell.removeAttribute('t')
    if formula is not None:
        child(doc, cell, 'f', formula)
    if value is None:
        return
    if isinstance(value, str):
        cell.setAttribute('t', 'inlineStr')
        child(doc, child(doc, cell, 'is'), 't', value)
    else:
        child(doc, cell, 'v', format(value, '.15g'))


def row_copy(source, index):
    row = source.cloneNode(True)
    row.setAttribute('r', str(index))
    for c in elements(row, 'c'):
        c.setAttribute('r', re.sub(r'\d+$', str(index), c.getAttribute('r')))
    return row


def fill_sheet(data, points, title, secondary=False, valves=None):
    doc = DOM.parseString(data)
    sheet_data = elements(doc, 'sheetData')[0]
    rows = {int(r.getAttribute('r')): r for r in elements(sheet_data, 'row')}
    start, old_end = (6, 13) if secondary else (5, 26)
    end = start + len(points) - 1
    if start not in rows or old_end not in rows:
        raise ValueError('선택한 파일이 지원하는 관로종단도 양식과 다릅니다.')
    prototype = rows[start + 1]
    new_rows = [r.cloneNode(True) for i, r in rows.items() if i < start]
    for i, (distance, elevation) in enumerate(points):
        number = start + i
        sample = rows[start] if i == 0 else rows[old_end] if i == len(points)-1 else prototype
        row = row_copy(sample, number)
        for col in ('ABCDEFGHIJKL' if secondary else 'ABCDEFGHIJ'):
            write_cell(doc, row, col)
        delta = distance - points[i-1][0] if i else 0
        write_cell(doc, row, 'A', i + 1)
        write_cell(doc, row, 'B', f'J-{i+1}')
        write_cell(doc, row, 'C', elevation)
        if secondary:
            main_row = 5 + i
            for col, val in [('C', elevation), ('D', distance), ('E', delta)]:
                write_cell(doc, row, col, val, f"'관로종단도'!{col}{main_row}")
        else:
            write_cell(doc, row, 'D', distance)
            write_cell(doc, row, 'E', delta, '0' if i == 0 else f'D{number}-D{number-1}')
        if not secondary and valves and i in valves:
            write_cell(doc, row, 'H', valves[i]['av'])
            write_cell(doc, row, 'I', valves[i]['station'])
        new_rows.append(row)
    if not secondary:
        total = row_copy(rows[27], end + 1)
        write_cell(doc, total, 'E', points[-1][0]-points[0][0], f'SUM(E5:E{end})')
        new_rows.append(total)
        for merge in elements(doc, 'mergeCell'):
            if merge.getAttribute('ref') == 'A27:B27':
                merge.setAttribute('ref', f'A{end+1}:B{end+1}')
    # Preserve the template's trailing empty rows, adjusted for the inserted records.
    for i, row in rows.items():
        if i > old_end + (0 if secondary else 1):
            new_rows.append(row_copy(row, i + len(points) - (old_end-start+1)))
    clear(sheet_data)
    for row in new_rows:
        sheet_data.appendChild(row)
    by_index = {int(r.getAttribute('r')): r for r in new_rows}
    if secondary:
        write_cell(doc, by_index[3], 'L')
    else:
        write_cell(doc, by_index[1], 'A', title)
        write_cell(doc, by_index[3], 'A')
        write_cell(doc, by_index[3], 'J')
    elements(doc, 'dimension')[0].setAttribute('ref', f'A1:{"L" if secondary else "Q"}{max(by_index)}')
    return doc.toxml(encoding='utf-8')


def update_chart(data, points, title):
    doc = DOM.parseString(data)
    for ref in elements(doc, 'c:strRef') + elements(doc, 'c:numRef'):
        formulas = elements(ref, 'c:f')
        if not formulas:
            continue
        formula = ''.join(n.data for n in formulas[0].childNodes if n.nodeType == n.TEXT_NODE)
        if '$A$1' in formula:
            values = [title]
            new_formula = "'관로종단도'!$A$1"
        elif '$B$5' in formula:
            values = [f'J-{i+1}' for i in range(len(points))]
            new_formula = f"'관로종단도'!$B$5:$B${len(points)+4}"
        elif '$C$5' in formula:
            values = [p[1] for p in points]
            new_formula = f"'관로종단도'!$C$5:$C${len(points)+4}"
        else:
            continue
        clear(formulas[0])
        formulas[0].appendChild(doc.createTextNode(new_formula))
        numeric = ref.tagName == 'c:numRef'
        for cache in elements(ref, 'c:numCache') + elements(ref, 'c:strCache'):
            ref.removeChild(cache)
        cache = child(doc, ref, 'c:numCache' if numeric else 'c:strCache')
        if numeric:
            child(doc, cache, 'c:formatCode', '0.0')
        child(doc, cache, 'c:ptCount', val=len(values))
        for i, value in enumerate(values):
            child(doc, child(doc, cache, 'c:pt', idx=i), 'c:v', value)
    # Original fixed -5..15 bounds would hide these sources (elevations > 23).
    for axis in elements(doc, 'c:valAx'):
        for tag in ('c:min', 'c:max', 'c:majorUnit', 'c:minorUnit'):
            for node in elements(axis, tag):
                node.parentNode.removeChild(node)
    return doc.toxml(encoding='utf-8')


def create_report(template, destination, points, title, valves=None):
    if not points or len(points) > 100000:
        raise ValueError('데이터는 1~100,000개여야 합니다.')
    destination = Path(destination)
    with ZipFile(BytesIO(read_bytes(template))) as archive:
        parts = {n: archive.read(n) for n in archive.namelist()}
    book = DOM.parseString(parts['xl/workbook.xml'])
    names = [s.getAttribute('name') for s in elements(book, 'sheet')]
    if names != ['관로종단도', '수공양식 ', 'Sheet2', 'Sheet3']:
        raise ValueError('제공된 광양시 관로종단도와 동일한 시트 구조의 양식을 선택해주세요.')
    parts['xl/worksheets/sheet1.xml'] = fill_sheet(parts['xl/worksheets/sheet1.xml'], points, title, valves=valves)
    parts['xl/worksheets/sheet2.xml'] = fill_sheet(parts['xl/worksheets/sheet2.xml'], points, title, True)
    parts['xl/charts/chart2.xml'] = update_chart(parts['xl/charts/chart2.xml'], points, title)
    for name in elements(book, 'definedName'):
        if name.getAttribute('name') == '_xlnm.Print_Area' and name.getAttribute('localSheetId') == '0':
            clear(name)
            name.appendChild(book.createTextNode(f"'관로종단도'!$A$1:$J${len(points)+5}"))
    calc = elements(book, 'calcPr')
    if calc:
        calc[0].setAttribute('fullCalcOnLoad', '1')
        calc[0].setAttribute('forceFullCalc', '1')
    parts['xl/workbook.xml'] = book.toxml(encoding='utf-8')
    # Old calculation-chain addresses no longer describe the extended table.
    parts.pop('xl/calcChain.xml', None)
    for part, tag, attr, value in [
        ('xl/_rels/workbook.xml.rels', 'Relationship', 'Type', '/calcChain'),
        ('[Content_Types].xml', 'Override', 'PartName', '/xl/calcChain.xml'),
    ]:
        doc = DOM.parseString(parts[part])
        for node in elements(doc, tag):
            if node.getAttribute(attr).endswith(value):
                node.parentNode.removeChild(node)
        parts[part] = doc.toxml(encoding='utf-8')
    buffer = BytesIO()
    with ZipFile(buffer, 'w', compression=8) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation guarantees that no input, template or prior result is replaced.
    with destination.open('xb') as stream:
        stream.write(buffer.getvalue())
    return destination


def convert_file(source, template, output_dir, log=lambda _: None, edits=None):
    profiles = read_profiles(source, log)
    created = []
    base = Path(source).stem.removeprefix('결과_')
    for i, (profile_name, points) in enumerate(profiles, 1):
        rows = merge_valves(points, (edits or {}).get(profile_name, []))
        points = [(r["distance"], r["elevation"]) for r in rows]
        valves = {j: r for j, r in enumerate(rows) if r["av"]}
        title = base + (f' 종단{i}' if len(profiles) > 1 else '')
        stem = re.sub(r'[<>:"/\\|?*]', '_', title) + '_관로종단도'
        destination = Path(output_dir) / f'{stem}.xlsx'
        serial = 1
        while destination.exists():
            destination = Path(output_dir) / f'{stem}_{serial}.xlsx'
            serial += 1
        create_report(template, destination, points, title, valves=valves)
        log(f'완료: {destination.name} ({len(points)}개 점)')
        created.append(destination)
    return created
