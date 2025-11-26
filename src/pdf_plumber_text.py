import os
import re
from typing import List, Dict, Any


def merge_lines_into_paragraphs(lines: List[str]) -> List[str]:
    """
    将连续行合并为段落，同时识别标题（如 1、1.1、1.1.1）
    """
    paragraphs = []
    buffer = []

    for line in lines:
        if not line.strip():
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
            continue

        # 识别标题（1、1.1、1.1.1）
        if re.match(r"^\d+(\.\d+)*\s+", line):
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
            paragraphs.append(line.strip())
        else:
            buffer.append(line.strip())

    if buffer:
        paragraphs.append(" ".join(buffer))

    return paragraphs


def extract_title_level(text: str) -> str:
    """
    提取标题级别，如 1、1.1、1.1.1
    """
    m = re.match(r"^(\d+(\.\d+)*)\s+", text)
    return m.group(1) if m else ""


def clean_cell_text(cell: str) -> str:
    """
    清理表格单元格:
    - 去掉换行 \n 和制表符 \t
    - 替换全角空格为半角空格
    - 合并连续空格
    - 去除首尾空白
    """
    if not cell:
        return ""
    cell = cell.replace("\u3000", " ")
    cell = re.sub(r"[\n\t]", " ", cell)
    cell = re.sub(r"\s+", " ", cell)
    return cell.strip()


def detect_field_table(headers: List[str]) -> bool:
    """
    简单判断是否为字段定义表
    """
    field_keywords = {"字段名", "定义", "类型", "格式", "示例"}
    header_set = set([h.lower() for h in headers])
    return bool(field_keywords & header_set)


def extract_fields_from_table(rows: List[List[str]]) -> List[Dict[str, str]]:
    """
    将字段表转换为结构化 JSON
    假设第一行是表头
    """
    if not rows:
        return []

    headers = [h.lower() for h in rows[0]]
    result = []
    for row in rows[1:]:
        if not any(row):
            continue
        item = {}
        for idx, val in enumerate(row):
            if idx >= len(headers):
                continue
            key = headers[idx]
            item[key] = val
        result.append(item)
    return result


def reconstruct_table_with_spans(page_obj, raw_table_rows: List[List[str]], table_settings: Dict[str, Any]) -> Dict[str, Any]:
    rows = [[clean_cell_text(c) for c in r] for r in raw_table_rows]
    meta = {"strategy": "downfill"}
    try:
        found = page_obj.find_tables(table_settings=table_settings)
        if found:
            meta["strategy"] = "geometry+downfill"
    except Exception:
        pass
    if rows and rows[0]:
        for j in range(len(rows[0])):
            last = None
            for i in range(len(rows)):
                v = rows[i][j]
                if v:
                    last = v
                else:
                    if last:
                        rows[i][j] = last
    return {"rows": rows, "meta": meta}


def build_row_groups(rows: List[List[str]]) -> List[Dict[str, Any]]:
    if not rows:
        return []
    headers = rows[0]
    data = rows[1:]
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in data:
        if not any(r):
            continue
        key = r[0] if r and r[0] else "未命名"
        item = {headers[i]: (r[i] if i < len(r) else "") for i in range(1, len(headers))}
        groups.setdefault(key, []).append(item)
    return [{"group": k, "rows": v} for k, v in groups.items()]


def read_pdf_plumber_text(path: str) -> List[Dict[str, Any]]:
    """
    PDF 内容结构化提取
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "Missing dependency pdfplumber. Install via: pip install pdfplumber"
        )

    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    output = []

    with pdfplumber.open(path) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text() or ""
            lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]

            # 段落和标题
            paragraphs = merge_lines_into_paragraphs(lines)
            for p in paragraphs:
                level = extract_title_level(p)
                is_title = bool(level)
                output.append(
                    {
                        "page": page_idx,
                        "type": "title" if is_title else "paragraph",
                        "level": level,
                        "text": p,
                    }
                )

            # 表格
            try:
                tables = page.extract_tables()
            except:
                tables = []

            # 可调表格几何识别参数
            DEFAULT_TABLE_SETTINGS = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance": 3,
                "join_tolerance": 3,
                "intersection_tolerance": 3,
            }

            for tb in tables:
                recon = reconstruct_table_with_spans(page, tb, DEFAULT_TABLE_SETTINGS)
                clean_rows = recon["rows"]
                groups = build_row_groups(clean_rows)

                # 检测是否为字段表
                fields = []
                if clean_rows and detect_field_table(clean_rows[0]):
                    fields = extract_fields_from_table(clean_rows)

                output.append(
                    {
                        "page": page_idx,
                        "type": "table",
                        "rows": clean_rows,
                        "groups": groups,
                        "fields": fields,
                    }
                )

    return output


if __name__ == "__main__":
    pdf_path = "guide/交通运输主数据（1.0版）(1).converted.pdf"
    fragments: List[Dict[str, Any]] = []
    try:
        fragments = read_pdf_plumber_text(pdf_path)
    except FileNotFoundError:
        synthetic_rows = [
            ["维度", "类别", "数据项", "系统", "频率", "部门"],
            ["路线", "基本信息", "路线基本信息", "公路养护统计报送系统", "每年", "公路局"],
            ["", "阻断信息", "路线阻断信息", "全国公路出行信息服务系统", "实时", "公路局"],
        ]
        # 向下填充以模拟竖向合并效果
        if synthetic_rows and synthetic_rows[0]:
            for j in range(len(synthetic_rows[0])):
                last = None
                for i in range(len(synthetic_rows)):
                    v = synthetic_rows[i][j]
                    if v:
                        last = v
                    else:
                        if last:
                            synthetic_rows[i][j] = last
        recon = {"rows": synthetic_rows, "meta": {"strategy": "synthetic+downfill"}}
        groups = build_row_groups(recon["rows"])
        fragments = [
            {"page": 0, "type": "table", "rows": recon["rows"], "groups": groups, "fields": []}
        ]

    import json

    with open("debug_pdf_output.json", "w", encoding="utf-8") as f:
        json.dump(fragments, f, ensure_ascii=False, indent=2)

    print(f"[DEBUG] 提取了 {len(fragments)} 内容段落/表格")
