import json
import os
from typing import Dict, List


def load_taxonomies(domain_dir: str) -> List[Dict]:
    files = [f for f in os.listdir(domain_dir) if f.endswith('.taxonomy.json')]
    items = []
    for f in files:
        with open(os.path.join(domain_dir, f), 'r', encoding='utf-8') as fp:
            taxonomy = json.load(fp)
            items.append(taxonomy)
    return items


def _tree_to_map(tree: List[Dict]) -> Dict[str, Dict[str, Dict[str, set]]]:
    m: Dict[str, Dict[str, Dict[str, set]]] = {}
    for root in tree or []:
        l1 = root.get('level1') or ''
        if not l1:
            continue
        m1 = m.setdefault(l1, {})
        for c2 in root.get('children', []) or []:
            l2 = c2.get('level2') or ''
            if not l2:
                continue
            m2 = m1.setdefault(l2, {})
            for c3 in c2.get('children', []) or []:
                l3 = c3.get('level3') or ''
                if not l3:
                    continue
                s4 = m2.setdefault(l3, set())
                for c4 in c3.get('children', []) or []:
                    l4 = c4.get('level4') or ''
                    if l4:
                        s4.add(l4)
    return m


def _map_to_tree(m: Dict[str, Dict[str, Dict[str, set]]]) -> List[Dict]:
    out = []
    for l1 in sorted(m.keys()):
        node1 = {'level1': l1, 'children': []}
        for l2 in sorted(m[l1].keys()):
            node2 = {'level2': l2, 'children': []}
            for l3 in sorted(m[l1][l2].keys()):
                node3 = {'level3': l3, 'children': []}
                level4s = sorted(list(m[l1][l2][l3]))
                node3['children'] = [{'level4': l4} for l4 in level4s]
                node2['children'].append(node3)
            node1['children'].append(node2)
        out.append(node1)
    return out


def merge_taxonomies(taxonomies: List[Dict]) -> Dict:
    levels: Dict[str, str] = {}
    merged_map: Dict[str, Dict[str, Dict[str, set]]] = {}
    for tx in taxonomies:
        for lv in tx.get('levels_definition', []) or []:
            code = (lv.get('code') or '').strip()
            desc = (lv.get('description') or '').strip()
            if not code:
                continue
            if code not in levels or (desc and len(desc) > len(levels.get(code, ''))):
                levels[code] = desc
        tmap = _tree_to_map(tx.get('tree') or [])
        for l1, m1 in tmap.items():
            mm1 = merged_map.setdefault(l1, {})
            for l2, m2 in m1.items():
                mm2 = mm1.setdefault(l2, {})
                for l3, s4 in m2.items():
                    ss4 = mm2.setdefault(l3, set())
                    ss4.update(s4)
    merged_levels = [{'code': k, 'description': levels[k]} for k in sorted(levels.keys())]
    merged_tree = _map_to_tree(merged_map)
    return {'levels_definition': merged_levels, 'tree': merged_tree}


def write_merged(domain_dir: str, merged: Dict):
    out_tax = os.path.join(domain_dir, 'taxonomy.merged.json')
    with open(out_tax, 'w', encoding='utf-8') as fp:
        json.dump(merged, fp, ensure_ascii=False, indent=2)
    # 同时写 seeds，便于后续直接使用
    paths = []
    for root in merged.get('tree') or []:
        l1 = root.get('level1') or ''
        for c2 in root.get('children', []) or []:
            l2 = c2.get('level2') or ''
            for c3 in c2.get('children', []) or []:
                l3 = c3.get('level3') or ''
                for c4 in c3.get('children', []) or []:
                    l4 = c4.get('level4') or ''
                    paths.append({'level1': l1, 'level2': l2, 'level3': l3, 'level4': l4})
    seeds = {'levels': merged.get('levels_definition', []), 'paths': paths}
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
