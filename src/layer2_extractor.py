import json
import os
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from llm_client import chat
from prompt_examples import get_layer2_examples

# 关键词常量（需在函数调用前定义）
GENERIC_KEYWORDS = [
    "身份证",
    "居民身份证",
    "统一社会信用代码",
    "手机号",
    "电话",
    "联系电话",
    "邮箱",
    "电子邮箱",
    "地址",
    "住址",
    "家庭关系",
    "营业收入",
    "岗位",
    "职称",
    "注册日期",
    "账户",
    "交易",
    "流水",
    "IP",
    "URL",
    "网址",
    "车牌",
    "司机",
    "线路",
    "单位",
    "联系人",
]

DOMAIN_EXTRA = {
    "finance": ["账户", "交易", "流水", "银行卡", "授信", "客户"],
    "meteorology": ["站号", "气象", "温度", "降水", "风速"],
    "government": ["居民", "户籍", "社保", "医保", "税号"],
    "traffic": ["车牌", "司机", "线路", "路段", "里程", "站点"],
    "science": [],
}


def group_paths(
    paths: List[Dict], by_levels=("level1", "level2"), batch_size: int = 20
) -> List[List[Dict]]:
    buckets = {}
    for p in paths:
        key = tuple(p.get(l, "") for l in by_levels)
        buckets.setdefault(key, []).append(p)
    groups = []
    for _, arr in buckets.items():
        for i in range(0, len(arr), batch_size):
            groups.append(arr[i : i + batch_size])
    return groups


def filter_fragments_for_group(
    paths: List[Dict],
    fragments: List[Dict],
    domain: str,
    per_path_limit: int = 3,
    group_limit: int = 12,
) -> List[Dict]:
    union = []
    for p in paths:
        union.extend(
            filter_fragments_for_path(p, fragments, domain, limit=per_path_limit)
        )
    seen = set()
    dedup = []
    for f in union:
        page = f.get("page")
        k = (page, (f.get("text") or "")[:64])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(f)
    return dedup[:group_limit]


def extract_structured(
    seeds: Dict, fragments: List[Dict], domain: str, source: str
) -> Dict:
    print(f"[DEBUG] Layer2 开始结构化抽取")
    print(f"[DEBUG] 域名: {domain}")
    print(f"[DEBUG] 来源: {source}")
    print(f"[DEBUG] 文本片段数量: {len(fragments)}")

    use_paths = bool(seeds.get("paths"))
    seed_count = len(seeds.get("levels", [])) + (
        len(seeds.get("paths", [])) if use_paths else len(seeds.get("categories", []))
    )
    print(f"[DEBUG] 种子数量: {seed_count}")

    if use_paths:
        system = (
            "你是数据分类分级抽取器Agent。根据给定的四级路径(paths)与相关片段，"
            "把每个路径下的最小数据项进行枚举与分级。"
            "说明：item 指可在字段/口径上落地的最小数据单元，例如 '身份证号'、'手机号'、'URL'、'IP'、'电子邮箱(员工)' 等；"
            "每个 level4 只需提供一次 citation 作为该路径的证据，items 不需要单独 citation。"
            "输出严格JSON: {domain, source, extraction}。extraction为列表，项结构:"
            "{path:{level1,level2,level3,level4}, citation:{page,text}, items:[{name, level(S1~S4), conditions[], exceptions[]}]}。"
            "若无法在片段中找到明确证据，请仍返回该路径并设置 citation.text 为最接近的依据，同时将不确定的 item 标注 exceptions=['needs_review']。"
            "禁止输出非JSON。"
        )
    else:
        system = (
            "你是数据分类分级抽取器Agent。根据taxonomy-seeds与原始标准片段，"
            "输出严格JSON: {domain, source, extraction}。extraction包含List项，每项结构:"
            "{category, level, conditions(List), exceptions(List?), citation({page,text})}."
            "禁止输出非JSON。"
        )

    user = json.dumps(
        {"domain": domain, "seeds": seeds, "fragments": fragments}, ensure_ascii=False
    )
    print(f"[DEBUG] 发送请求到LLM，输入数据长度: {len(user)} 字符")
    examples = get_layer2_examples(domain)
    messages = (
        [{"role": "system", "content": system}]
        + examples
        + [{"role": "user", "content": user}]
    )
    content = chat(messages)
    print(f"[DEBUG] LLM响应长度: {len(content)} 字符")

    s = content.find("{")
    e = content.rfind("}")
    if s == -1 or e == -1:
        raise RuntimeError("LLM未返回JSON")
    json_str = content[s : e + 1]
    print(f"[DEBUG] 提取的JSON长度: {len(json_str)} 字符")
    obj = json.loads(json_str)
    obj["domain"] = domain
    obj["source"] = source
    extraction_count = len(obj.get("extraction", []))
    print(f"[DEBUG] 抽取出 {extraction_count} 条结构化规则")
    return obj


def run_for_artifact_dir(artifact_dir: str, base: str, domain: str):
    print(f"\n[DEBUG] Layer2 处理工件目录: {artifact_dir}")
    print(f"[DEBUG] 基础文件名: {base}")
    print(f"[DEBUG] 域名: {domain}")

    seeds_path = os.path.join(artifact_dir, f"{base}.taxonomy_seeds.json")
    frags_path = os.path.join(artifact_dir, f"{base}.fragments.json")

    print(f"[DEBUG] 读取种子文件: {seeds_path}")
    with open(seeds_path, "r", encoding="utf-8") as f:
        seeds = json.load(f)

    print(f"[DEBUG] 读取片段文件: {frags_path}")
    with open(frags_path, "r", encoding="utf-8") as f:
        fragments = json.load(f)

    source = os.path.join("guide", base + ".pdf")

    use_paths = bool(seeds.get("paths"))
    if use_paths:
        print(f"[DEBUG] 使用四级路径分组抽取")
        batch_size = int(os.environ.get("L2_BATCH_SIZE", "20") or "20")
        per_path_limit = int(os.environ.get("L2_PER_PATH_FRAG_LIMIT", "3") or "3")
        group_limit = int(os.environ.get("L2_GROUP_FRAG_LIMIT", "12") or "12")
        workers = int(os.environ.get("L2_WORKERS", "5") or "5")
        groups = group_paths(seeds.get("paths", []), ("level1", "level2"), batch_size)
        print(
            f"[DEBUG] 分成 {len(groups)} 组，每组最多 {batch_size} 条路径，并行度 {workers}"
        )
        all_items = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futures = []
            for gi, group in enumerate(groups, 1):
                mini_seeds = {"levels": seeds.get("levels", []), "paths": group}
                frags = filter_fragments_for_group(
                    group,
                    fragments,
                    domain,
                    per_path_limit=per_path_limit,
                    group_limit=group_limit,
                )
                futures.append(
                    ex.submit(extract_structured, mini_seeds, frags, domain, source)
                )
            for fi, fut in enumerate(as_completed(futures), 1):
                try:
                    extraction = fut.result()
                    items = extraction.get("extraction", [])
                    print(
                        f"[DEBUG] 并行分组 {fi}/{len(futures)} 抽取到 {len(items)} 项"
                    )
                    all_items.extend(items)
                except Exception as e:
                    print(f"[DEBUG] 分组任务失败: {e}")
        result = {"domain": domain, "source": source, "extraction": all_items}
        fname = f"{base}.extraction.detailed.json"
        out_path = os.path.join(artifact_dir, fname)
        print(f"[DEBUG] 保存抽取结果到: {out_path}")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] 抽取完成: {out_path}")
    else:
        print(f"[DEBUG] 使用旧模式抽取（无paths）")
        extraction = extract_structured(seeds, fragments, domain, source)
        fname = f"{base}.extraction.json"
        out_path = os.path.join(artifact_dir, fname)
        print(f"[DEBUG] 保存抽取结果到: {out_path}")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(extraction, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] 抽取完成: {out_path}")


def filter_fragments_for_path(
    path: Dict, fragments: List[Dict], domain: str, limit: int = 6
) -> List[Dict]:
    tokens = [
        path.get("level1", ""),
        path.get("level2", ""),
        path.get("level3", ""),
        path.get("level4", ""),
    ]
    kws = set([t for t in tokens if t])
    for k in GENERIC_KEYWORDS:
        kws.add(k)
    for k in DOMAIN_EXTRA.get(domain, []):
        kws.add(k)
    scored = []
    for frag in fragments:
        text = frag.get("text", "") or ""
        score = 0
        for k in kws:
            if k and (k in text):
                score += 1
        if score > 0:
            scored.append((score, frag))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored[:limit]] or fragments[: min(limit, len(fragments))]


def main():
    print(f"[DEBUG] Layer2 主程序开始执行")

    root = os.path.dirname(os.path.dirname(__file__))
    artifacts = os.path.join(root, "artifacts")
    print(f"[DEBUG] 工件目录: {artifacts}")

    if not os.path.exists(artifacts):
        print(f"[DEBUG] 工件目录不存在，退出")
        return

    domains = [
        d for d in os.listdir(artifacts) if os.path.isdir(os.path.join(artifacts, d))
    ]
    print(f"[DEBUG] 找到 {len(domains)} 个域: {domains}")

    for domain in domains:
        artifact_dir = os.path.join(artifacts, domain)
        print(f"\n[DEBUG] 处理域: {domain}")

        files = [
            f for f in os.listdir(artifact_dir) if f.endswith(".taxonomy_seeds.json")
        ]
        print(f"[DEBUG] 找到 {len(files)} 个种子文件: {files}")

        for i, f in enumerate(files, 1):
            base = f.replace(".taxonomy_seeds.json", "")
            print(f"\n[DEBUG] 处理第 {i}/{len(files)} 个种子文件: {f}")
            run_for_artifact_dir(artifact_dir, base, domain)

    print(f"\n[DEBUG] Layer2 主程序执行完成")


if __name__ == "__main__":
    main()
