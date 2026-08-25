#!/usr/bin/env python3
"""Create a salary-inclusive resume variant with a narrow OOXML patch.

The current resume is treated as the authoritative source. The source file is
never overwritten. Only the career-summary table, footer placeholder, and field
refresh setting are changed in the new DOCX package.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DOCX = ROOT / "output" / "documents" / "정채민_국문이력서_2026.docx"
OUTPUT_DOCX = ROOT / "output" / "documents" / "정채민_국문이력서_2026_연봉포함.docx"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS}
qn = lambda name: f"{{{W_NS}}}{name}"

EXPECTED_HEADER = ["기간", "회사 / 직급", "주요 업무"]
NEW_HEADER = ["기간", "회사 / 직급", "연봉(만원)", "주요 업무"]
NEW_WIDTHS_DXA = [2050, 2150, 1300, 4472]
SALARY_BY_COMPANY = {
    "플로우테크(주)": "3,400",
    "(주)리팩": "3,800",
    "(주)엘리비젼": "3,400",
}


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def parse_xml(data: bytes):
    return etree.fromstring(data, parser=etree.XMLParser(remove_blank_text=False))


def serialize_xml(root) -> bytes:
    return etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        standalone=True,
    )


def cell_text(cell) -> str:
    return "".join(cell.xpath(".//w:t/text()", namespaces=NS)).strip()


def table_header(table) -> list[str]:
    rows = table.xpath("./w:tr", namespaces=NS)
    if not rows:
        return []
    return [cell_text(cell) for cell in rows[0].xpath("./w:tc", namespaces=NS)]


def replace_cell_text(cell, value: str) -> None:
    text_nodes = cell.xpath(".//w:t", namespaces=NS)
    if not text_nodes:
        paragraphs = cell.xpath("./w:p", namespaces=NS)
        paragraph = paragraphs[0] if paragraphs else etree.SubElement(cell, qn("p"))
        run = etree.SubElement(paragraph, qn("r"))
        text = etree.SubElement(run, qn("t"))
        text.text = value
        return

    text_nodes[0].text = value
    text_nodes[0].set(f"{{{XML_NS}}}space", "preserve")
    for node in text_nodes[1:]:
        node.text = ""


def set_cell_width(cell, width_dxa: int) -> None:
    tc_pr = cell.find(qn("tcPr"))
    if tc_pr is None:
        tc_pr = etree.Element(qn("tcPr"))
        cell.insert(0, tc_pr)
    tc_w = tc_pr.find(qn("tcW"))
    if tc_w is None:
        tc_w = etree.Element(qn("tcW"))
        tc_pr.insert(0, tc_w)
    tc_w.set(qn("type"), "dxa")
    tc_w.set(qn("w"), str(width_dxa))


def patch_career_table(document_xml: bytes) -> bytes:
    root = parse_xml(document_xml)
    matches = [
        table
        for table in root.xpath(".//w:tbl", namespaces=NS)
        if table_header(table) == EXPECTED_HEADER
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one career summary table, found {len(matches)}")

    table = matches[0]
    tbl_w = table.find("./w:tblPr/w:tblW", namespaces=NS)
    if tbl_w is None or int(tbl_w.get(qn("w"), "0")) != sum(NEW_WIDTHS_DXA):
        raise AssertionError("Career table width does not match the retained template")

    grid = table.find(qn("tblGrid"))
    if grid is None:
        raise AssertionError("Career table has no tblGrid")
    for child in list(grid):
        grid.remove(child)
    for width in NEW_WIDTHS_DXA:
        grid_col = etree.SubElement(grid, qn("gridCol"))
        grid_col.set(qn("w"), str(width))

    rows = table.xpath("./w:tr", namespaces=NS)
    if len(rows) != 4:
        raise AssertionError(f"Expected header plus three career rows, found {len(rows)}")

    for row_index, row in enumerate(rows):
        cells = row.xpath("./w:tc", namespaces=NS)
        if len(cells) != 3:
            raise AssertionError(f"Career row {row_index + 1} has {len(cells)} cells")

        new_cell = deepcopy(cells[1])
        if row_index == 0:
            new_value = "연봉(만원)"
        else:
            company = cell_text(cells[1])
            matches_for_company = [
                salary for key, salary in SALARY_BY_COMPANY.items() if key in company
            ]
            if len(matches_for_company) != 1:
                raise AssertionError(f"Salary mapping failed for career row: {company}")
            new_value = matches_for_company[0]

        replace_cell_text(new_cell, new_value)
        cells[2].addprevious(new_cell)

        updated_cells = row.xpath("./w:tc", namespaces=NS)
        for cell, width in zip(updated_cells, NEW_WIDTHS_DXA, strict=True):
            set_cell_width(cell, width)

    return serialize_xml(root)


def add_run_properties(run, *, bold: bool = False) -> None:
    r_pr = etree.SubElement(run, qn("rPr"))
    fonts = etree.SubElement(r_pr, qn("rFonts"))
    for name in ("ascii", "hAnsi", "cs"):
        fonts.set(qn(name), "Arial")
    fonts.set(qn("eastAsia"), "맑은 고딕")
    if bold:
        etree.SubElement(r_pr, qn("b"))
    color = etree.SubElement(r_pr, qn("color"))
    color.set(qn("val"), "66727C")
    size = etree.SubElement(r_pr, qn("sz"))
    size.set(qn("val"), "16")


def append_text_run(paragraph, text_value: str, *, bold: bool = False) -> None:
    run = etree.SubElement(paragraph, qn("r"))
    add_run_properties(run, bold=bold)
    text = etree.SubElement(run, qn("t"))
    text.text = text_value
    if text_value.startswith(" ") or text_value.endswith(" "):
        text.set(f"{{{XML_NS}}}space", "preserve")


def append_tab_run(paragraph) -> None:
    run = etree.SubElement(paragraph, qn("r"))
    add_run_properties(run)
    etree.SubElement(run, qn("tab"))


def append_field(paragraph, field_code: str, result_text: str) -> None:
    begin_run = etree.SubElement(paragraph, qn("r"))
    add_run_properties(begin_run)
    begin = etree.SubElement(begin_run, qn("fldChar"))
    begin.set(qn("fldCharType"), "begin")

    instr_run = etree.SubElement(paragraph, qn("r"))
    add_run_properties(instr_run)
    instr = etree.SubElement(instr_run, qn("instrText"))
    instr.set(f"{{{XML_NS}}}space", "preserve")
    instr.text = f" {field_code} "

    separate_run = etree.SubElement(paragraph, qn("r"))
    add_run_properties(separate_run)
    separate = etree.SubElement(separate_run, qn("fldChar"))
    separate.set(qn("fldCharType"), "separate")

    result_run = etree.SubElement(paragraph, qn("r"))
    add_run_properties(result_run)
    result = etree.SubElement(result_run, qn("t"))
    result.text = result_text

    end_run = etree.SubElement(paragraph, qn("r"))
    add_run_properties(end_run)
    end = etree.SubElement(end_run, qn("fldChar"))
    end.set(qn("fldCharType"), "end")


def patch_footer(footer_xml: bytes) -> bytes:
    root = parse_xml(footer_xml)

    # Remove Word's empty footer placeholder content control.
    for sdt in root.xpath("./w:sdt", namespaces=NS):
        root.remove(sdt)

    paragraphs = root.xpath("./w:p", namespaces=NS)
    if not paragraphs:
        paragraph = etree.SubElement(root, qn("p"))
        p_pr = etree.SubElement(paragraph, qn("pPr"))
        border = etree.SubElement(etree.SubElement(p_pr, qn("pBdr")), qn("bottom"))
        border.set(qn("val"), "single")
        border.set(qn("sz"), "4")
        border.set(qn("space"), "3")
        border.set(qn("color"), "D7E0E6")
        tabs = etree.SubElement(p_pr, qn("tabs"))
        tab = etree.SubElement(tabs, qn("tab"))
        tab.set(qn("val"), "right")
        tab.set(qn("pos"), "10092")
    else:
        paragraph = paragraphs[-1]
        for child in list(paragraph):
            if child.tag != qn("pPr"):
                paragraph.remove(child)

    append_text_run(paragraph, "정채민 | 국문 이력서")
    append_tab_run(paragraph)
    append_field(paragraph, "PAGE", "1")
    append_text_run(paragraph, " / ")
    append_field(paragraph, "NUMPAGES", "2")
    return serialize_xml(root)


def patch_settings(settings_xml: bytes) -> bytes:
    root = parse_xml(settings_xml)
    update_fields = root.find(qn("updateFields"))
    if update_fields is None:
        update_fields = etree.SubElement(root, qn("updateFields"))
    update_fields.set(qn("val"), "true")
    return serialize_xml(root)


def write_variant(source: Path, output: Path) -> None:
    source_hash_before = file_hash(source)
    with ZipFile(source, "r") as source_zip:
        document_xml = patch_career_table(source_zip.read("word/document.xml"))
        footer_xml = patch_footer(source_zip.read("word/footer1.xml"))
        settings_xml = patch_settings(source_zip.read("word/settings.xml"))

        output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as output_zip:
            output_zip.comment = source_zip.comment
            for item in source_zip.infolist():
                data = source_zip.read(item.filename)
                if item.filename == "word/document.xml":
                    data = document_xml
                elif item.filename == "word/footer1.xml":
                    data = footer_xml
                elif item.filename == "word/settings.xml":
                    data = settings_xml
                output_zip.writestr(item, data)

    if file_hash(source) != source_hash_before:
        raise AssertionError("Source resume changed during variant creation")


def package_hashes(path: Path) -> dict[str, str]:
    with ZipFile(path) as archive:
        return {
            name: sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
        }


def validate_variant(source: Path, output: Path) -> None:
    if not output.exists() or output.stat().st_size < 10_000:
        raise AssertionError(f"Output DOCX was not created correctly: {output}")

    source_parts = package_hashes(source)
    output_parts = package_hashes(output)
    if set(source_parts) != set(output_parts):
        raise AssertionError("DOCX package parts changed unexpectedly")

    changed_parts = {
        name for name in source_parts if source_parts[name] != output_parts[name]
    }
    expected_changed = {"word/document.xml", "word/footer1.xml", "word/settings.xml"}
    if changed_parts != expected_changed:
        raise AssertionError(f"Unexpected package changes: {sorted(changed_parts)}")

    with ZipFile(output) as archive:
        document = parse_xml(archive.read("word/document.xml"))
        footer = parse_xml(archive.read("word/footer1.xml"))
        settings = parse_xml(archive.read("word/settings.xml"))

    tables = [
        table
        for table in document.xpath(".//w:tbl", namespaces=NS)
        if table_header(table) == NEW_HEADER
    ]
    if len(tables) != 1:
        raise AssertionError(f"Expected one salary table, found {len(tables)}")

    table = tables[0]
    rows = table.xpath("./w:tr", namespaces=NS)
    actual_rows = [[cell_text(cell) for cell in row.xpath("./w:tc", namespaces=NS)] for row in rows]
    expected_rows = [
        NEW_HEADER,
        [
            "2025.12.18 - 2026.06.21",
            "플로우테크(주) / 주임",
            "3,400",
            "Pipe2012 수충격 해석, CAD·수리계산서 검토, 기술보고서 및 대외 기술협의",
        ],
        [
            "2022.02.14 - 2024.04.10",
            "(주)리팩 / 사원",
            "3,800",
            "로터리 자동 포장기계 조립, 부품 가공·용접, 유압 및 기본 전기배선",
        ],
        [
            "2017.10 - 2017.12",
            "(주)엘리비젼 / 현장실습",
            "3,400",
            "키오스크 제작·부품 조립, 품질 확인, 현장 점검 및 A/S 보조",
        ],
    ]
    if actual_rows != expected_rows:
        raise AssertionError(f"Salary table content mismatch: {actual_rows}")

    tbl_w = table.find("./w:tblPr/w:tblW", namespaces=NS)
    grid = [
        int(col.get(qn("w"), "0"))
        for col in table.xpath("./w:tblGrid/w:gridCol", namespaces=NS)
    ]
    if tbl_w is None or int(tbl_w.get(qn("w"), "0")) != sum(grid):
        raise AssertionError("Salary table width and grid do not match")
    if grid != NEW_WIDTHS_DXA:
        raise AssertionError(f"Salary table grid mismatch: {grid}")
    for row_index, row in enumerate(rows, start=1):
        widths = [
            int(cell.find("./w:tcPr/w:tcW", namespaces=NS).get(qn("w"), "0"))
            for cell in row.xpath("./w:tc", namespaces=NS)
        ]
        if widths != grid:
            raise AssertionError(f"Salary table row {row_index} width mismatch: {widths}")

    footer_text = "".join(footer.xpath(".//w:t/text()", namespaces=NS))
    footer_fields = " ".join(footer.xpath(".//w:instrText/text()", namespaces=NS))
    if "[여기에 입력]" in footer_text or "정채민 | 국문 이력서" not in footer_text:
        raise AssertionError(f"Footer placeholder was not repaired: {footer_text}")
    if "PAGE" not in footer_fields or "NUMPAGES" not in footer_fields:
        raise AssertionError(f"Footer page fields are missing: {footer_fields}")

    update_fields = settings.find(qn("updateFields"))
    if update_fields is None or update_fields.get(qn("val")) != "true":
        raise AssertionError("Word field refresh setting is missing")

    forbidden = "\n".join(
        document.xpath(".//w:t/text()", namespaces=NS)
        + footer.xpath(".//w:t/text()", namespaces=NS)
    )
    if "[여기에 입력]" in forbidden:
        raise AssertionError("Visible placeholder text remains")

    print(f"Created: {output}")
    print(f"Source SHA-256 preserved: {file_hash(source)}")
    print(f"Output size: {output.stat().st_size} bytes")
    print(f"Changed package parts: {sorted(changed_parts)}")
    print("Salary values: 플로우테크 3,400 / 리팩 3,800 / 엘리비젼 3,400 (만원)")
    print("Footer placeholder: repaired")
    print("Table geometry: verified")


def main() -> None:
    if not SOURCE_DOCX.exists():
        raise FileNotFoundError(SOURCE_DOCX)
    write_variant(SOURCE_DOCX, OUTPUT_DOCX)
    validate_variant(SOURCE_DOCX, OUTPUT_DOCX)


if __name__ == "__main__":
    main()
