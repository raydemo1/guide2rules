from typing import Dict, List, Any


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).replace("\u3000", " ").strip()


def _clean_header_cells(cells: List[str]) -> List[str]:
    out: List[str] = []
    for c in cells:
        t = _norm(c)
        t = t.replace("\n", " ").replace("\t", " ")
        t = " ".join([p for p in t.split(" ") if p])
        out.append(t)
    return out


def _normalize_header(headers: List[str]) -> List[str]:
    h = _clean_header_cells(headers)
    merged: List[str] = []
    i = 0
    while i < len(h):
        cur = h[i].lower()
        nxt = h[i + 1].lower() if i + 1 < len(h) else ""
        if cur == "主数据" and nxt == "名称":
            merged.append("主数据名称")
            i += 2
            continue
        if cur == "数据来" and nxt == "源系统":
            merged.append("数据来源系统")
            i += 2
            continue
        merged.append(h[i])
        i += 1
    return merged


def _header_map(headers: List[str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    alias: Dict[str, str] = {
        "主数据类别": "level1",
        "数据类别": "level1",
        "类别": "level1",
        "主数据名称": "md_name",
        "名称": "md_name",
        "数据项": "fieldname",
        "数据项说明": "fielddesc",
        "数据类型": "datatype",
        "数据格式": "format",
        "计量单位": "unit",
        "值域": "enum",
        "参考依据": "citation",
        "数据来源系统": "source_system",
        "更新频率": "update_frequency",
        "责任单位": "owner",
        "分级": "grade",
        "等级": "grade",
        "grade": "grade",
    }
    for idx, h in enumerate(headers):
        key = alias.get(h, "")
        if key:
            mapping[key] = idx
    return mapping


def _is_class_table(hm: Dict[str, int]) -> bool:
    return ("level1" in hm) or ("md_name" in hm)


def _is_field_table(hm: Dict[str, int]) -> bool:
    return ("fieldname" in hm) and not _is_class_table(hm)


def _extract_grade_codes(vals: List[str]) -> List[str]:
    codes: List[str] = []
    for v in vals:
        t = _norm(v).upper()
        for token in [p for p in t.replace("/", " ").split(" ") if p]:
            if token.startswith("S"):
                codes.append(token)
    return codes


def build_taxonomy_from_tables(fragments: List[Dict]) -> Dict:
    paths: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
    items_by_path: Dict[str, List[str]] = {}
    current_title_path: List[str] = []

    def _update_title_path(level_str: str, title_text: str):
        nonlocal current_title_path
        lvl = _norm(level_str)
        txt = _norm(title_text)
        if not txt:
            return
        depth = 0
        if lvl:
            try:
                depth = len([p for p in lvl.split(".") if p])
            except Exception:
                depth = 1
        else:
            depth = 1
        while len(current_title_path) < depth:
            current_title_path.append("")
        current_title_path = current_title_path[:depth]
        current_title_path[depth - 1] = txt

    for f in fragments:
        t = f.get("type")
        if t == "title":
            _update_title_path(_norm(f.get("level", "")), _norm(f.get("text", "")))
            continue
        if t != "table":
            continue
        headers = _normalize_header([_norm(c) for c in f.get("headers", [])])
        rows = f.get("rows") or []
        if not headers or not rows:
            continue
        hm = _header_map(headers)
        if not (_is_class_table(hm) or _is_field_table(hm)):
            continue
        

        for r in rows:
            lv1 = ""
            mdn = ""
            if "level1" in hm and hm["level1"] < len(r):
                lv1 = _norm(r[hm["level1"]])
            if not lv1 and current_title_path:
                lv1 = current_title_path[0]
            if "md_name" in hm and hm["md_name"] < len(r):
                mdn = _norm(r[hm["md_name"]])
            l1 = lv1
            l2 = mdn or (current_title_path[1] if len(current_title_path) > 1 else "")
            l3 = current_title_path[2] if len(current_title_path) > 2 else ""
            l4 = mdn or ""
            if not l1 and not l4:
                continue
            pkey = "|".join([l1, l2, l3, l4])
            items: List[str] = []
            if "fieldname" in hm and hm["fieldname"] < len(r):
                fname = _norm(r[hm["fieldname"]])
                if fname:
                    items.append(fname)
            if items:
                items_by_path.setdefault(pkey, [])
                items_by_path[pkey].extend(items)
            paths.setdefault(l1, {}).setdefault(l2, {}).setdefault(l3, [])
            if l4 and l4 not in paths[l1][l2][l3]:
                paths[l1][l2][l3].append(l4)

    for k in list(items_by_path.keys()):
        items_by_path[k] = sorted(list(set(items_by_path[k])))

    levels: List[Dict[str, Any]] = []

    tree: List[Dict] = []
    for l1 in sorted(paths.keys()):
        n1 = {"level": 1, "name": l1, "children": []}
        for l2 in sorted(paths[l1].keys()):
            n2 = {"level": 2, "name": l2, "children": []}
            for l3 in sorted(paths[l1][l2].keys()):
                n3 = {"level": 3, "name": l3, "children": []}
                for l4 in sorted(paths[l1][l2][l3]):
                    n3["children"].append({"level": 4, "name": l4})
                n2["children"].append(n3)
            n1["children"].append(n2)
        tree.append(n1)

    return {"levels_definition": levels, "tree": tree}


def build_pre_extracted_items(fragments: List[Dict], domain: str, source: str) -> Dict:
    extraction: List[Dict] = []
    current_title_path: List[str] = []

    def _update_title_path(level_str: str, title_text: str):
        nonlocal current_title_path
        lvl = _norm(level_str)
        txt = _norm(title_text)
        if not txt:
            return
        depth = 0
        if lvl:
            try:
                depth = len([p for p in lvl.split(".") if p])
            except Exception:
                depth = 1
        else:
            depth = 1
        while len(current_title_path) < depth:
            current_title_path.append("")
        current_title_path = current_title_path[:depth]
        current_title_path[depth - 1] = txt

    for f in fragments:
        if f.get("type") == "title":
            _update_title_path(_norm(f.get("level", "")), _norm(f.get("text", "")))
            continue
        if f.get("type") != "table":
            continue
        headers = _normalize_header([_norm(c) for c in f.get("headers", [])])
        rows = f.get("rows") or []
        if not headers or not rows:
            continue
        hm = _header_map(headers)
        if not (_is_class_table(hm) or _is_field_table(hm)):
            continue
        for r in rows:
            lv1 = ""
            mdn = ""
            if "level1" in hm and hm["level1"] < len(r):
                lv1 = _norm(r[hm["level1"]])
            if not lv1 and current_title_path:
                lv1 = current_title_path[0]
            if "md_name" in hm and hm["md_name"] < len(r):
                mdn = _norm(r[hm["md_name"]])
            path = {
                "level1": lv1 or "",
                "level2": mdn or (current_title_path[1] if len(current_title_path) > 1 else ""),
                "level3": current_title_path[2] if len(current_title_path) > 2 else "",
                "level4": mdn or "",
            }
            item_name = ""
            if "fieldname" in hm and hm["fieldname"] < len(r):
                item_name = _norm(r[hm["fieldname"]])
            if not item_name and not mdn:
                continue
            level_code = ""
            metadata = {
                "fielddesc": _norm(r[hm["fielddesc"]]) if "fielddesc" in hm and hm["fielddesc"] < len(r) else "",
                "datatype": _norm(r[hm["datatype"]]) if "datatype" in hm and hm["datatype"] < len(r) else "",
                "format": _norm(r[hm["format"]]) if "format" in hm and hm["format"] < len(r) else "",
                "unit": _norm(r[hm["unit"]]) if "unit" in hm and hm["unit"] < len(r) else "",
                "enum": _norm(r[hm["enum"]]) if "enum" in hm and hm["enum"] < len(r) else "",
                "source_system": _norm(r[hm["source_system"]]) if "source_system" in hm and hm["source_system"] < len(r) else "",
                "update_frequency": _norm(r[hm["update_frequency"]]) if "update_frequency" in hm and hm["update_frequency"] < len(r) else "",
                "owner": _norm(r[hm["owner"]]) if "owner" in hm and hm["owner"] < len(r) else "",
                "citation_hint": _norm(r[hm["citation"]]) if "citation" in hm and hm["citation"] < len(r) else "",
            }
            items = []
            items.append({
                "name": item_name or mdn,
                "level": "",
                "conditions": [],
                "exceptions": [],
                "metadata": metadata,
            })
            extraction.append({
                "path": path,
                "items": items,
                "evidence_extracted": True,
            })
    return {"domain": domain, "source": source, "extraction": extraction}
