import json
import os
from typing import Dict, List


def load_glossary(path: str) -> Dict[str, str]:
    print(f"[DEBUG] Layer2_5 加载术语表: {path}")

    try:
        with open(path, 'r', encoding='utf-8') as fp:
            gloss = json.load(fp)
        print(f"[DEBUG] 成功加载术语表，包含 {len(gloss)} 个术语")
    except Exception as e:
        print(f"[DEBUG] 无法加载术语表: {e}")
        return {}

    mapping = {}
    for g in gloss:
        term = (g.get('term') or '').strip()
        if not term:
            continue

        mapping[term] = term
        synonyms = g.get('synonyms', []) or []
        for s in synonyms:
            sname = (s or '').strip()
            if sname:
                mapping[sname] = term

        if synonyms:
            print(f"[DEBUG] 术语: {term}, 同义词: {synonyms}")

    print(f"[DEBUG] 术语映射包含 {len(mapping)} 个条目")
    return mapping


def normalize_items(extraction: Dict, mapping: Dict[str, str]) -> Dict:
    print(f"[DEBUG] Layer2_5 规范化项目，输入抽取项数量: {len(extraction.get('extraction', []))}")

    out = []
    normalized_count = 0
    unchanged_count = 0

    for i, it in enumerate(extraction.get('extraction', []), 1):
        # 支持分组结构：items 列表 + 共享 citation
        if isinstance(it.get('items'), list):
            path = it.get('path', {})
            citation = it.get('citation', {})
            for sub in it['items']:
                name = (sub.get('name') or '').strip()
                canon = mapping.get(name) or name
                if canon != name:
                    normalized_count += 1
                else:
                    unchanged_count += 1
                out.append({
                    'path': path,
                    'item': {'name': name, 'canonical': canon},
                    'level': sub.get('level', ''),
                    'conditions': sub.get('conditions', []) or [],
                    'exceptions': sub.get('exceptions', []) or [],
                    'citation': citation
                })
        else:
            name = (it.get('item', {}).get('name') or it.get('field') or '').strip()
            canon = mapping.get(name) or name
            if canon != name:
                normalized_count += 1
            else:
                unchanged_count += 1
            it['item'] = it.get('item') or {}
            it['item']['canonical'] = canon
            out.append(it)

    extraction['extraction'] = out

    print(f"[DEBUG] 规范化完成: {normalized_count} 项被规范化，{unchanged_count} 项保持不变")
    return extraction


def main():
    print(f"[DEBUG] Layer2_5 主程序开始执行")

    root = os.path.dirname(os.path.dirname(__file__))
    artifacts = os.path.join(root, 'artifacts')
    print(f"[DEBUG] 工件目录: {artifacts}")

    domains = [d for d in os.listdir(artifacts) if os.path.isdir(os.path.join(artifacts, d))]
    print(f"[DEBUG] 找到 {len(domains)} 个域: {domains}")

    total_files_processed = 0

    for domain in domains:
        print(f"\n[DEBUG] ========== 处理域: {domain} ==========")
        domain_dir = os.path.join(artifacts, domain)

        files = [f for f in os.listdir(domain_dir) if f.endswith('.extraction.detailed.json')]
        print(f"[DEBUG] 找到 {len(files)} 个详细抽取文件: {files}")

        for i, f in enumerate(files, 1):
            print(f"\n[DEBUG] 处理第 {i}/{len(files)} 个文件: {f}")

            base = f.replace('.extraction.detailed.json', '')
            gloss_path = os.path.join(domain_dir, f'{base}.glossary.json')

            print(f"[DEBUG] 术语表路径: {gloss_path}")
            mapping = load_glossary(gloss_path)

            print(f"[DEBUG] 读取抽取文件: {f}")
            with open(os.path.join(domain_dir, f), 'r', encoding='utf-8') as fp:
                ext = json.load(fp)

            norm = normalize_items(ext, mapping)

            out_path = os.path.join(domain_dir, f'{base}.items.normalized.json')
            print(f"[DEBUG] 保存规范化结果到: {out_path}")

            with open(out_path, 'w', encoding='utf-8') as fp:
                json.dump(norm, fp, ensure_ascii=False, indent=2)

            print(f"[DEBUG] 文件处理完成: {out_path}")
            total_files_processed += 1

    print(f"\n[DEBUG] Layer2_5 主程序执行完成，共处理 {total_files_processed} 个文件")


if __name__ == '__main__':
    main()
