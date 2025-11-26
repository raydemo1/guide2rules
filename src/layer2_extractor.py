import json
import os
import sys
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from llm_client import chat
from prompt_examples import get_layer2_examples


def _load_keywords_config():
    override = os.environ.get("L2_KEYWORDS_CONFIG") or ""
    root = os.path.dirname(os.path.dirname(__file__))
    cfg_path = (
        override if override else os.path.join(root, "config", "layer2_keywords.json")
    )
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("generic", []) or [], cfg.get("domain_extra", {}) or {}
    except Exception:
        return [
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
        ], {
            "finance": ["账户", "交易", "流水", "银行卡", "授信", "客户"],
            "meteorology": ["站号", "气象", "温度", "降水", "风速"],
            "government": ["居民", "户籍", "社保", "医保", "税号"],
            "transportation": ["车牌", "司机", "线路", "路段", "里程", "站点"],
            "science": [],
        }


GENERIC_KEYWORDS, DOMAIN_EXTRA = _load_keywords_config()


def _load_params_config():
    override = os.environ.get("L2_PARAMS_CONFIG") or ""
    root = os.path.dirname(os.path.dirname(__file__))
    cfg_path = (
        override if override else os.path.join(root, "config", "layer2_params.json")
    )
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return {
                "workers": int(cfg.get("workers", 5)),
                "batch_size": int(cfg.get("batch_size", 20)),
                "per_path_frag_limit": int(cfg.get("per_path_frag_limit", 3)),
                "group_frag_limit": int(cfg.get("group_frag_limit", 12)),
            }
    except Exception:
        return {
            "workers": int(os.environ.get("L2_WORKERS", "5") or "5"),
            "batch_size": int(os.environ.get("L2_BATCH_SIZE", "20") or "20"),
            "per_path_frag_limit": int(
                os.environ.get("L2_PER_PATH_FRAG_LIMIT", "3") or "3"
            ),
            "group_frag_limit": int(
                os.environ.get("L2_GROUP_FRAG_LIMIT", "12") or "12"
            ),
        }


 


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


def _load_grouping_config():
    override = os.environ.get("L2_GROUPING_CONFIG") or ""
    root = os.path.dirname(os.path.dirname(__file__))
    cfg_path = (
        override if override else os.path.join(root, "config", "layer2_grouping.json")
    )
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return {
                "group_by_depth": int(cfg.get("group_by_depth", 2)),
                "path_token_depths": list(cfg.get("path_token_depths", [0, 1, 2, 3])),
            }
    except Exception:
        return {"group_by_depth": 2, "path_token_depths": [0, 1, 2, 3]}


def _get_path_segments(p: Dict) -> List[str]:
    if isinstance(p.get("path"), list):
        return [str(x or "").strip() for x in p["path"]]
    return [
        str(p.get("level1", "") or "").strip(),
        str(p.get("level2", "") or "").strip(),
        str(p.get("level3", "") or "").strip(),
        str(p.get("level4", "") or "").strip(),
    ]


def group_paths_variable(
    paths: List[Dict], depth: int, batch_size: int
) -> List[List[Dict]]:
    buckets = {}
    for p in paths:
        segs = _get_path_segments(p)
        key = tuple(segs[: max(1, depth)])
        buckets.setdefault(key, []).append(p)
    groups = []
    for _, arr in buckets.items():
        for i in range(0, len(arr), batch_size):
            groups.append(arr[i : i + batch_size])
    return groups


def _call_llm_and_parse(messages: List[Dict], domain: str, source: str) -> Dict:
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


def _build_system_prompt_for_extraction() -> str:
    return (
        "你是数据分类分级抽取器Agent。根据给定的路径与相关片段，"
        "请为每个item生成分级(level: Sx 或 Sx-n)与匹配信息 patterns:{keywords[], regex[]}。"
        "路径为可变层级数组 path:[seg1,seg2,...]，按指南实际深度返回，允许3–5层，不得填充或复制末级。"
        "必须严格按输入 seeds.paths 的出现顺序返回 extraction 列表中的项，不得重排。"
        "输出严格JSON: {domain, source, extraction}。extraction为列表，项结构:"
        "{path:[seg1,seg2,...], citation:{page,text}, items:[{name, level, patterns:{keywords[], regex[]}}]}。"
        "禁止输出非JSON。"
    )


def _build_user_payload_for_extraction(domain: str, seeds: Dict, fragments: List[Dict]) -> str:
    return json.dumps({"domain": domain, "seeds": seeds, "fragments": fragments}, ensure_ascii=False)


 


 


def _build_messages(system: str, user: str, domain: str, with_examples: bool) -> List[Dict]:
    if with_examples:
        examples = get_layer2_examples(domain)
        return ([{"role": "system", "content": system}] + examples + [{"role": "user", "content": user}])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _make_order_map(paths: List[Dict]) -> Dict[tuple, int]:
    order = {}
    for idx, p in enumerate(paths):
        segs = _get_path_segments(p)
        order[tuple(segs)] = idx
    return order


def _path_tuple(obj: Dict) -> tuple:
    segs = obj.get("path") or []
    return tuple(segs) if isinstance(segs, list) else tuple()


def _sort_items_by_order(items: List[Dict], order_map: Dict[tuple, int]) -> List[Dict]:
    return sorted(items, key=lambda it: order_map.get(_path_tuple(it), float("inf")))


def extract_structured(
    seeds: Dict, fragments: List[Dict], domain: str, source: str
) -> Dict:
    print(f"[DEBUG] Layer2 开始结构化抽取")
    print(f"[DEBUG] 域名: {domain}")
    print(f"[DEBUG] 来源: {source}")
    print(f"[DEBUG] 文本片段数量: {len(fragments)}")

    use_paths = bool(seeds.get("paths"))
    seed_count = len(seeds.get("levels", [])) + len(seeds.get("paths", []))
    print(f"[DEBUG] 种子数量: {seed_count}")
    has_seed_items = any(
        isinstance(p, dict) and bool(p.get("items")) for p in seeds.get("paths", [])
    )

    if not use_paths:
        raise RuntimeError("seeds.paths 为空，已移除旧模式")
    system = _build_system_prompt_for_extraction()
    user = _build_user_payload_for_extraction(domain, seeds, fragments)
    print(f"[DEBUG] 发送请求到LLM，输入数据长度: {len(user)} 字符")
    messages = _build_messages(system, user, domain, with_examples=True)
    return _call_llm_and_parse(messages, domain, source)


 


def run_for_artifact_dir(artifact_dir: str, base: str, domain: str):
    print(f"\n[DEBUG] Layer2 处理工件目录: {artifact_dir}")
    print(f"[DEBUG] 基础文件名: {base}")
    print(f"[DEBUG] 域名: {domain}")

    if base.endswith(".merged"):
        reviewed = os.path.join(artifact_dir, "taxonomy_seeds.reviewed.json")
        seeds_path = reviewed if os.path.exists(reviewed) else os.path.join(artifact_dir, "taxonomy_seeds.merged.json")
        # 合并所有 fragments 作为上下文
        frag_files = [
            f
            for f in os.listdir(artifact_dir)
            if f.endswith(".fragments.json")
        ]
        merged_frags = []
        for ff in frag_files:
            try:
                with open(os.path.join(artifact_dir, ff), "r", encoding="utf-8") as f:
                    merged_frags.extend(json.load(f) or [])
            except Exception:
                pass
        frags_path = None
    else:
        reviewed = os.path.join(artifact_dir, f"{base}.taxonomy_seeds.reviewed.json")
        seeds_path = reviewed if os.path.exists(reviewed) else os.path.join(artifact_dir, f"{base}.taxonomy_seeds.json")
        frags_path = os.path.join(artifact_dir, f"{base}.fragments.json")

    # 统一走LLM抽取路径，不再读取预抽取items

    print(f"[DEBUG] 读取种子文件: {seeds_path}")
    with open(seeds_path, "r", encoding="utf-8") as f:
        seeds = json.load(f)

    if base.endswith(".merged"):
        fragments = merged_frags
        print(f"[DEBUG] 使用合并片段，共 {len(fragments)} 条")
    else:
        print(f"[DEBUG] 读取片段文件: {frags_path}")
        with open(frags_path, "r", encoding="utf-8") as f:
            fragments = json.load(f)

    source = "merged" if base.endswith(".merged") else os.path.join("guide", base + ".pdf")

    use_paths = bool(seeds.get("paths"))
    if not use_paths or not seeds.get("paths"):
        print(f"[DEBUG] seeds.paths 为空，已移除旧模式，跳过该文件")
        return
    else:
        print(f"[DEBUG] 使用路径分组抽取（兼容可变层级）")
        params = _load_params_config()
        grouping = _load_grouping_config()
        batch_size = params["batch_size"]
        per_path_limit = params["per_path_frag_limit"]
        group_limit = params["group_frag_limit"]
        workers = params["workers"]
        raw_paths = seeds.get("paths", [])
        norm_paths = raw_paths
        groups = group_paths_variable(
            norm_paths, grouping.get("group_by_depth", 2), batch_size
        )
        print(
            f"[DEBUG] 分成 {len(groups)} 组，每组最多 {batch_size} 条路径，并行度 {workers}"
        )
        order_map = _make_order_map(seeds.get("paths", []))
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
                    items = _sort_items_by_order(items, order_map)
                    print(f"[DEBUG] 并行分组 {fi}/{len(futures)} 抽取到 {len(items)} 项")
                    all_items.extend(items)
                except Exception as e:
                    print(f"[DEBUG] 分组任务失败: {e}")
        result_items = _sort_items_by_order(all_items, order_map)
        result = {"domain": domain, "source": source, "extraction": result_items}
        fname = f"{base}.extraction.detailed.json"
        out_path = os.path.join(artifact_dir, fname)
        print(f"[DEBUG] 保存抽取结果到: {out_path}")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] 抽取完成: {out_path}")


def filter_fragments_for_path(
    path: Dict, fragments: List[Dict], domain: str, limit: int = 6
) -> List[Dict]:
    grouping = _load_grouping_config()
    segs = _get_path_segments(path)
    depths = grouping.get("path_token_depths", [0, 1, 2, 3])
    tokens = [segs[d] for d in depths if d < len(segs)]
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
    # 支持命令行指定域，例如: python src/layer2_extractor.py transportation
    if len(sys.argv) > 1:
        wanted = sys.argv[1].strip()
        if wanted in domains:
            domains = [wanted]
            print(f"[DEBUG] 指定处理域: {wanted}")
        else:
            print(f"[DEBUG] 指定域不存在: {wanted}，可用域: {domains}")
            return
    print(f"[DEBUG] 找到 {len(domains)} 个域: {domains}")

    for domain in domains:
        artifact_dir = os.path.join(artifacts, domain)
        print(f"\n[DEBUG] 处理域: {domain}")
        merged_seeds = os.path.join(artifact_dir, "taxonomy_seeds.merged.json")
        if os.path.exists(merged_seeds):
            print(f"[DEBUG] 检测到 merged 种子，仅处理: taxonomy_seeds.merged.json")
            run_for_artifact_dir(artifact_dir, "taxonomy_seeds.merged", domain)
        else:
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
