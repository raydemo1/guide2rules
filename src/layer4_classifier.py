import os
import sys
import json
import argparse
from typing import Dict, List, Any
import openpyxl
from tqdm import tqdm

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from business_rules.engine import run_all
from rules.variables import ClassificationVariables
from rules.actions import ClassificationActions


def load_rules(domain: str, root: str) -> Dict[str, List[Dict]]:
    """加载分类与分级规则并分开返回，支持两阶段执行"""
    cat_path = os.path.join(root, "rules", domain, "categorization_rules.json")
    cls_path = os.path.join(root, "rules", domain, "classification_rules.json")

    cat_rules: List[Dict] = []
    cls_rules: List[Dict] = []

    if os.path.exists(cat_path):
        with open(cat_path, "r", encoding="utf-8") as f:
            cat_rules = json.load(f)

    if os.path.exists(cls_path):
        with open(cls_path, "r", encoding="utf-8") as f:
            cls_rules = json.load(f)

    print(f"[INFO] Loaded rules: categorization={len(cat_rules)}, classification={len(cls_rules)}, total={len(cat_rules)+len(cls_rules)}")
    return {"cat": cat_rules, "cls": cls_rules}


def detect_columns(headers: List[str]) -> Dict[str, int]:
    hmap = {str(h or "").strip(): i for i, h in enumerate(headers)}

    def find(candidates: List[str]) -> int:
        for k in candidates:
            if k in hmap:
                return hmap[k]
        return -1

    # 字段注释即中文字段名；若无则回退至“字段名/字段名称/名称”
    field_idx = find(["字段注释", "字段名", "FieldName", "字段名称", "名称"])
    category_idx = find(["分类路径", "Category", "分类"])
    # 字段样本仅对应数据示例
    value_idx = find(["字段样本", "样本", "数据示例"])  # 兼容可能的表头变体
    return {"field": field_idx, "category": category_idx, "value": value_idx}


def normalize_category(category: str) -> str:
    s = str(category or "").strip()
    s = s.replace("\\", "/")
    s = "/".join([p.strip() for p in s.split("/") if p.strip()])
    return s


def classify_rows(
    domain: str,
    in_path: str,
    out_path: str,
    category_override: str,
    stop_first: bool,
    sheet_name: str,
):
    root = os.path.dirname(os.path.dirname(__file__))
    try:
        rl = load_rules(domain, root)
        cat_rules = rl.get("cat", [])
        cls_rules = rl.get("cls", [])
        print(f"[DEBUG] Loaded rules from {domain}: cat={len(cat_rules)}, cls={len(cls_rules)}")
    except Exception as e:
        print(f"[ERROR] Failed to load rules: {e}")
        return

    wb = openpyxl.load_workbook(in_path)
    ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

    headers = [
        str(c.value or "").strip() for c in next(ws.iter_rows(min_row=1, max_row=1))
    ]
    cols = detect_columns(headers)

    # 调试打印列索引
    print(f"[DEBUG] Column mapping: {cols}")

    rows = []
    for row in ws.iter_rows(min_row=2):
        rows.append([c.value for c in row])

    new_headers = headers + ["分类路径", "分级", "规则ID", "审计"]
    out_wb = openpyxl.Workbook()
    out_ws = out_wb.active
    out_ws.title = ws.title
    out_ws.append(new_headers)

    total_rows = len(rows)
    matched_rows = 0
    for r in tqdm(rows, desc=f"[PROGRESS] {os.path.basename(in_path)}", unit="row"):
        field_name = str((r[cols["field"]] if cols["field"] >= 0 else "") or "").strip()
        if cols["category"] >= 0:
            # 修复：不直接使用输入的分类，留给规则引擎处理
            category = normalize_category(r[cols["category"]])
        else:
            category = normalize_category(category_override)

        # 仅使用“字段样本”作为数据示例；缺失则为空
        if cols["value"] >= 0:
            v = r[cols["value"]]
            value_text = str(v) if v is not None else ""
        else:
            value_text = ""

        # 关键修复：创建变量对象时，category_path使用输入值（规则会覆盖）
        obj = {
            "field_name": field_name,
            "category_path": category,  # 规则执行后会覆盖
            "value_text": value_text,
        }

        vars_obj = ClassificationVariables(obj)
        acts_obj = ClassificationActions(obj)

        # 阶段1：仅分类
        if cat_rules:
            run_all(
                rule_list=cat_rules,
                defined_variables=vars_obj,
                defined_actions=acts_obj,
                stop_on_first_trigger=bool(stop_first),
            )

        # 阶段2：仅分级（依赖已写入的 category_path）
        if cls_rules:
            run_all(
                rule_list=cls_rules,
                defined_variables=vars_obj,
                defined_actions=acts_obj,
                stop_on_first_trigger=bool(stop_first),
            )

        final_category = obj.get("category_path", "")
        level = obj.get("result_level", "")
        rid = obj.get("result_rule_id", "")
        audits = obj.get("audits", [])
        audit_str = (
            ";".join([json.dumps(a, ensure_ascii=False) for a in audits])
            if audits
            else ""
        )

        # 统计匹配情况：若分类路径发生变化，或产生分级/规则ID，则视为命中规则
        if (final_category and final_category != category) or level or rid:
            matched_rows += 1

        # 修复：输出规则执行后的分类路径
        out_ws.append([*r, final_category, level, rid, audit_str])

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out_wb.save(out_path)
    print(f"[INFO] Saved result to: {out_path}")

    # 末尾调试统计信息
    ratio = (matched_rows / total_rows) if total_rows > 0 else 0.0
    print(
        f"[INFO] Stats: total_rows={total_rows}, matched_rows={matched_rows}, matched_ratio={ratio:.2%}"
    )


def process_domain(
    domain: str,
    input_file: str,
    category_override: str,
    stop_first: bool,
    sheet_name: str,
):
    root = os.path.dirname(os.path.dirname(__file__))
    if input_file:
        base = os.path.splitext(os.path.basename(input_file))[0]
        out_dir = os.path.join(root, "outputs", domain)
        out_path = os.path.join(out_dir, base + ".classified.xlsx")
        classify_rows(
            domain, input_file, out_path, category_override, stop_first, sheet_name
        )
        print(out_path)
        return

    in_dir = os.path.join(root, "test", "data", domain)
    if not os.path.exists(in_dir):
        print(f"[ERROR] Input directory not found: {in_dir}")
        return

    files = [f for f in os.listdir(in_dir) if f.lower().endswith(".xlsx")]
    print(f"[DEBUG] Found files: {files}")
    for f in tqdm(files, desc=f"[FILES] {domain}", unit="file"):
        in_path = os.path.join(in_dir, f)
        base = os.path.splitext(f)[0]
        out_dir = os.path.join(root, "outputs", domain)
        out_path = os.path.join(out_dir, base + ".classified.xlsx")
        classify_rows(
            domain, in_path, out_path, category_override, stop_first, sheet_name
        )
        print(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("domain")
    parser.add_argument("--input", dest="input", default=None)
    parser.add_argument("--category", dest="category", default="")
    parser.add_argument("--stop-first", dest="stop_first", default="false")
    parser.add_argument("--sheet", dest="sheet", default="")
    args = parser.parse_args()

    stop_first = str(args.stop_first).lower() != "false"
    process_domain(args.domain, args.input, args.category, stop_first, args.sheet)


if __name__ == "__main__":
    main()
