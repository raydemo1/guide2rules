import json
import os
from typing import Dict, List, Any
from business_rules import export_rule_data

from rules.variables import ClassificationVariables
from rules.actions import ClassificationActions


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_extractions(domain_dir: str) -> List[str]:
    files = []
    for f in os.listdir(domain_dir):
        if f.endswith(".extraction.json") or f.endswith(".extraction.detailed.json"):
            files.append(os.path.join(domain_dir, f))
    return files


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()


def _level_rank(level: str) -> int:
    m = {"s1": 1, "s2": 2, "s3": 3, "s4": 4}
    return m.get(_norm(level).lower(), 0)


def resolve_conflicts(rows: List[Dict]) -> List[Dict]:
    buckets: Dict[str, Dict] = {}
    for r in rows:
        key = _norm(r.get("FieldName")) + "|" + _norm(r.get("Category"))
        if not key:
            continue
        cur = buckets.get(key)
        if not cur:
            buckets[key] = r
            continue

        priority_cur = int(r.get("Priority", 60))
        priority_cur_old = int(cur.get("Priority", 60))

        if priority_cur < priority_cur_old:
            buckets[key] = r
        elif priority_cur == priority_cur_old:
            cond_cur = _norm(r.get("ConditionExpression"))
            cond_old = _norm(cur.get("ConditionExpression"))
            if cond_cur and cond_old:
                r["ConditionExpression"] = f"{cond_old} OR {cond_cur}"

            exc_cur = _norm(r.get("ExceptionExpression"))
            exc_old = _norm(cur.get("ExceptionExpression"))
            if exc_cur and exc_old:
                r["ExceptionExpression"] = f"{exc_old} OR {exc_cur}"

            # 合并关键词
            kw_cur = [
                x.strip()
                for x in (_norm(r.get("PatternKeywords")) or "").split(",")
                if x
            ]
            kw_old = [
                x.strip()
                for x in (_norm(cur.get("PatternKeywords")) or "").split(",")
                if x
            ]
            if kw_cur and kw_old:
                r["PatternKeywords"] = ",".join(set(kw_cur + kw_old))

            # 合并正则
            rx_cur = [
                x.strip() for x in (_norm(r.get("PatternRegex")) or "").split("||") if x
            ]
            rx_old = [
                x.strip()
                for x in (_norm(cur.get("PatternRegex")) or "").split("||")
                if x
            ]
            if rx_cur and rx_old:
                r["PatternRegex"] = "||".join(set(rx_cur + rx_old))

            buckets[key] = r
    return list(buckets.values())


def build_categorization_rules(combined: List[Dict]) -> List[Dict]:
    category_groups = {}

    for r in combined:
        category = _norm(r.get("Category"))
        if not category:
            continue

        keywords_str = r.get("PatternKeywords", "")
        if not keywords_str:
            continue

        keywords = [kw.strip().lower() for kw in keywords_str.split(",") if kw.strip()]

        if category not in category_groups:
            category_groups[category] = []
        category_groups[category].extend(keywords)

    rules = []
    for category, keywords in category_groups.items():

        keywords = list(set(keywords))
        conditions = {
            "any": [
                {"name": "field_name", "operator": "contains", "value": kw}
                for kw in keywords
            ]
        }

        actions = [
            {"name": "set_suggested_category", "params": {"category": category}},
            {
                "name": "set_category_rule_id",
                "params": {"rule_id": f"C-{category[:10]}"},
            },
        ]

        rules.append({"conditions": conditions, "actions": actions})

    return rules


def build_classification_rules(combined: List[Dict]) -> List[Dict]:
    rules = []

    level_kw: Dict[str, set] = {}
    level_rx: Dict[str, set] = {}

    for r in combined:
        level = _norm(r.get("Level"))
        kws = [
            kw.lower()
            for kw in (_norm(r.get("PatternKeywords")) or "").split(",")
            if kw
        ]
        rxs = [rx for rx in (_norm(r.get("PatternRegex")) or "").split("||") if rx]

        if not level:
            continue
        if kws:
            level_kw.setdefault(level, set()).update(kws)
        if rxs:
            level_rx.setdefault(level, set()).update(rxs)

    for level in sorted(set(list(level_kw.keys()) + list(level_rx.keys()))):
        kws = sorted(list(level_kw.get(level, set())))
        rxs = sorted(list(level_rx.get(level, set())))
        if not kws or not rxs:
            continue

        conditions = {
            "all": [
                {"any": [
                    {"name": "field_name", "operator": "contains", "value": kw}
                    for kw in kws
                ]},
                {"any": [
                    {"name": "value_text", "operator": "matches_regex", "value": rx}
                    for rx in rxs
                ]},
            ]
        }

        actions = [
            {"name": "set_classification", "params": {"level": level, "rule_id": f"R-{level}"}},
            {"name": "append_audit", "params": {"citation": "", "source": f"aggregated::{level}"}},
        ]

        rules.append({"conditions": conditions, "actions": actions})

    return rules


def write_rules(
    domain: str,
    root: str,
    categorization_rules: List[Dict],
    classification_rules: List[Dict],
):
    out_dir = os.path.join(root, "rules", domain)
    os.makedirs(out_dir, exist_ok=True)

    # 写入分类规则
    cat_path = os.path.join(out_dir, "categorization_rules.json")
    with open(cat_path, "w", encoding="utf-8") as f:
        json.dump(categorization_rules, f, ensure_ascii=False, indent=2)

    # 写入分级规则
    cls_path = os.path.join(out_dir, "classification_rules.json")
    with open(cls_path, "w", encoding="utf-8") as f:
        json.dump(classification_rules, f, ensure_ascii=False, indent=2)

    # 导出变量/动作元数据
    data = export_rule_data(ClassificationVariables, ClassificationActions)
    with open(
        os.path.join(out_dir, "export_rule_data.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return cat_path, cls_path


def main():
    root = os.path.dirname(os.path.dirname(__file__))
    artifacts = os.path.join(root, "artifacts")
    domains = set()

    for path in [artifacts]:
        if os.path.isdir(path):
            domains.update(
                [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
            )

    for domain in sorted(domains):
        domain_artifacts = os.path.join(artifacts, domain)
        static_rows = []

        if os.path.isdir(domain_artifacts):
            for file in list_extractions(domain_artifacts):
                data = read_json(file)
                for item in data.get("extraction", []):
                    path = item.get("path", [])
                    category = "/".join([p for p in path if p])

                    for field in item.get("items", []):
                        keywords = field.get("patterns", {}).get("keywords", [])
                        regex = field.get("patterns", {}).get("regex", [])

                        static_rows.append(
                            {
                                "FieldName": field.get("name", ""),
                                "Category": category,
                                "Level": field.get("level", ""),
                                "PatternKeywords": ",".join(keywords),
                                "PatternRegex": "||".join(regex),
                                "Citation": json.dumps(
                                    item.get("citation", {}), ensure_ascii=False
                                ),
                                "Source": file,
                                "Priority": 50,
                            }
                        )

        # 2. 从动态规则文件合并
        dynamic_rows = []
        dynamic_dir = os.path.join(root, "excels", domain)
        if os.path.isdir(dynamic_dir):
            for file in os.listdir(dynamic_dir):
                if file.lower().endswith((".csv", ".xlsx")):
                    # 读取Excel文件（简化版，实际需用pandas或openpyxl）
                    # 这里用占位符表示
                    dynamic_rows.append(
                        {
                            "FieldName": file.split(".")[0],
                            "Category": f"dynamic/{domain}",
                            "Level": "S2",
                            "PatternKeywords": "dynamic_key",
                            "PatternRegex": "dynamic_rx",
                            "Citation": "dynamic_cit",
                            "Source": file,
                            "Priority": 60,
                        }
                    )

        # 3. 合并规则并解决冲突
        combined = resolve_conflicts(static_rows + dynamic_rows)

        # 4. 生成两类规则
        categorization_rules = build_categorization_rules(combined)
        classification_rules = build_classification_rules(combined)

        # 5. 写入规则文件
        cat_path, cls_path = write_rules(
            domain, root, categorization_rules, classification_rules
        )

        print(f"[{domain}] 分类规则生成: {cat_path}")
        print(f"[{domain}] 分级规则生成: {cls_path}")
        print(f"   - 分类规则数: {len(categorization_rules)}")
        print(f"   - 分级规则数: {len(classification_rules)}\n")


if __name__ == "__main__":
    main()
