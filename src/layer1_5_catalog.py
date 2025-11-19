import json
import os
from typing import Dict, List


def load_taxonomies(domain_dir: str) -> List[Dict]:
    print(f"[DEBUG] Layer1_5 加载分类体系文件，目录: {domain_dir}")

    files = [f for f in os.listdir(domain_dir) if f.endswith('.taxonomy.json')]
    print(f"[DEBUG] 找到 {len(files)} 个taxonomy文件: {files}")

    items = []
    for f in files:
        print(f"[DEBUG] 读取文件: {f}")
        with open(os.path.join(domain_dir, f), 'r', encoding='utf-8') as fp:
            taxonomy = json.load(fp)
            items.append(taxonomy)
            print(f"[DEBUG] 加载分类体系: {taxonomy.get('domain', '')} - {taxonomy.get('source', '')}")

    print(f"[DEBUG] 共加载 {len(items)} 个分类体系")
    return items


def build_catalog(taxonomies: List[Dict]) -> Dict:
    print(f"[DEBUG] Layer1_5 构建目录，输入分类体系数量: {len(taxonomies)}")

    catalog = {}
    total_items = 0

    for tx_idx, tx in enumerate(taxonomies, 1):
        print(f"[DEBUG] 处理第 {tx_idx}/{len(taxonomies)} 个分类体系")
        tree = tx.get('tree') or []
        print(f"[DEBUG] 树结构节点数量: {len(tree)}")

        def walk(node, p):
            if 'level1' in node:
                print(f"[DEBUG] 处理level1: {node.get('level1')}")
                for c2 in node.get('children', []):
                    walk({'level2': c2.get('level2'), 'children': c2.get('children', [])}, [node.get('level1')])
            elif 'level2' in node:
                print(f"[DEBUG] 处理level2: {node.get('level2')}")
                for c3 in node.get('children', []):
                    walk({'level3': c3.get('level3'), 'children': c3.get('children', [])}, p + [node.get('level2')])
            elif 'level3' in node:
                print(f"[DEBUG] 处理level3: {node.get('level3')}")
                for c4 in node.get('children', []):
                    lvl4 = c4.get('level4')
                    items = c4.get('items', [])
                    key = tuple(p + [lvl4])
                    bucket = catalog.setdefault(key, set())

                    for it in items:
                        name = it.get('name')
                        if name:
                            bucket.add(name)
                            total_items += 1

                    if items:
                        print(f"[DEBUG] level4: {lvl4}, 添加 {len(items)} 个项目到路径: {key}")

        for root in tree:
            walk(root, [])

    print(f"[DEBUG] 总共收集到 {total_items} 个项目")
    print(f"[DEBUG] 去重后有 {len(catalog)} 个唯一路径")

    out = []
    for key, vals in catalog.items():
        out.append({
            'level1': key[0] if len(key)>0 else '',
            'level2': key[1] if len(key)>1 else '',
            'level3': key[2] if len(key)>2 else '',
            'level4': key[3] if len(key)>3 else '',
            'items': sorted(list(vals))
        })

    print(f"[DEBUG] 生成的目录包含 {len(out)} 个路径")
    return {'paths': out}


def main():
    print(f"[DEBUG] Layer1_5 主程序开始执行")

    root = os.path.dirname(os.path.dirname(__file__))
    artifacts = os.path.join(root, 'artifacts')
    print(f"[DEBUG] 工件目录: {artifacts}")

    domains = [d for d in os.listdir(artifacts) if os.path.isdir(os.path.join(artifacts, d))]
    print(f"[DEBUG] 找到 {len(domains)} 个域: {domains}")

    for domain in domains:
        print(f"\n[DEBUG] ========== 处理域: {domain} ==========")
        domain_dir = os.path.join(artifacts, domain)
        print(f"[DEBUG] 域目录: {domain_dir}")

        taxonomies = load_taxonomies(domain_dir)
        if not taxonomies:
            print(f"[DEBUG] 域 {domain} 没有分类体系文件，跳过")
            continue

        cat = build_catalog(taxonomies)

        out_path = os.path.join(domain_dir, 'catalog.json')
        print(f"[DEBUG] 保存目录到: {out_path}")

        with open(out_path, 'w', encoding='utf-8') as fp:
            json.dump(cat, fp, ensure_ascii=False, indent=2)

        print(f"[DEBUG] 目录构建完成: {out_path}")

    print(f"\n[DEBUG] Layer1_5 主程序执行完成")


if __name__ == '__main__':
    main()

