import json
import os
from typing import Dict, List, Any


def load_taxonomies(domain_dir: str) -> List[Dict]:
    files = [f for f in os.listdir(domain_dir) if f.endswith('.taxonomy.json')]
    items = []
    for f in files:
        with open(os.path.join(domain_dir, f), 'r', encoding='utf-8') as fp:
            taxonomy = json.load(fp)
            items.append(taxonomy)
    return items


def _node_name(node: Dict[str, Any]) -> str:
    if 'name' in node:
        return (node.get('name') or '').strip()
    # 兼容 level1..levelN 命名
    for k in sorted(node.keys()):
        if k.startswith('level'):
            return (node.get(k) or '').strip()
    return ''


def _collect_paths(tree: List[Dict]) -> List[List[str]]:
    paths: List[List[str]] = []

    def walk(node: Dict[str, Any], acc: List[str]):
        if not isinstance(node, dict):
            return
        name = _node_name(node)
        cur = acc + ([name] if name else [])
        children = node.get('children') or []
        if children:
            for ch in children:
                walk(ch, cur)
        else:
            if cur:
                paths.append(cur)

    for root in tree or []:
        walk(root, [])
    return paths


def _merge_tree_nodes(trie: Dict[str, Any], node: Dict[str, Any], depth: int):
    name = _node_name(node)
    if not name:
        return
    cur = trie.setdefault(name, { 'level': int(node.get('level') or depth), 'items': set(), 'children': {} })
    lvl = int(node.get('level') or depth)
    # 统一level为最小深度或已有一致值
    cur['level'] = min(cur.get('level', lvl), lvl)
    # 合并items
    if isinstance(node.get('items'), list):
        for it in node['items']:
            s = str(it or '').strip()
            if s:
                cur['items'].add(s)
    # 递归children
    for ch in node.get('children') or []:
        _merge_tree_nodes(cur['children'], ch, depth + 1)


def _trie_to_tree(trie: Dict[str, Any]) -> List[Dict]:
    out: List[Dict] = []
    for name in trie.keys():
        rec = trie[name]
        node: Dict[str, Any] = { 'name': name, 'level': rec.get('level', 1) }
        if rec.get('children'):
            node['children'] = _trie_to_tree(rec['children'])
        if rec.get('items'):
            items_list = sorted(list(rec['items']))
            if items_list:
                node['items'] = items_list
        out.append(node)
    return out


def merge_taxonomies(taxonomies: List[Dict]) -> Dict:
    merged_levels = []
    for tx in taxonomies:
        for lv in tx.get('levels_definition', []) or []:
            merged_levels.append(lv)

    trie: Dict[str, Any] = {}
    for tx in taxonomies:
        for root in tx.get('tree') or []:
            _merge_tree_nodes(trie, root, depth=1)
    merged_tree = _trie_to_tree(trie)
    return { 'levels_definition': merged_levels, 'tree': merged_tree }


def _collect_path_items(tree: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    def walk(node: Dict[str, Any], acc: List[str]):
        name = _node_name(node)
        cur = acc + ([name] if name else [])
        children = node.get('children') or []
        if children:
            for ch in children:
                walk(ch, cur)
        else:
            if cur:
                items = []
                if isinstance(node.get('items'), list):
                    items = [str(x or '').strip() for x in node['items'] if str(x or '').strip()]
                entry: Dict[str, Any] = { 'path': cur }
                if items:
                    entry['items'] = items
                out.append(entry)
    for root in tree or []:
        walk(root, [])
    return out


def write_merged(domain_dir: str, merged: Dict):
    out_tax = os.path.join(domain_dir, 'taxonomy.merged.json')
    with open(out_tax, 'w', encoding='utf-8') as fp:
        json.dump(merged, fp, ensure_ascii=False, indent=2)
    # seeds 跟随layer1格式，包含items（如有）
    path_items = _collect_path_items(merged.get('tree') or [])
    seeds = {'levels': merged.get('levels_definition', []), 'paths': path_items}
    out_seeds = os.path.join(domain_dir, 'taxonomy_seeds.merged.json')
    with open(out_seeds, 'w', encoding='utf-8') as fp:
        json.dump(seeds, fp, ensure_ascii=False, indent=2)
    return out_tax, out_seeds


def main():
    root = os.path.dirname(os.path.dirname(__file__))
    artifacts = os.path.join(root, 'artifacts')
    domains = [d for d in os.listdir(artifacts) if os.path.isdir(os.path.join(artifacts, d))]
    for domain in domains:
        domain_dir = os.path.join(artifacts, domain)
        taxonomies = load_taxonomies(domain_dir)
        if not taxonomies:
            continue
        merged = merge_taxonomies(taxonomies)
        out_tax, out_seeds = write_merged(domain_dir, merged)
        print(out_tax)
        print(out_seeds)


if __name__ == '__main__':
    main()
