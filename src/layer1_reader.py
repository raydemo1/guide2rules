import json
import os
from typing import Dict, List

from pdf_text import read_pdf_text
from llm_client import chat
from prompt_examples import get_layer1_examples


DOMAINS = {
    "金融": "finance",
    "气象": "meteorology",
    "政务": "government",
    "政府": "government",
    "科学": "science",
    "科研": "science",
}


def detect_domain(filename: str) -> str:
    name = os.path.basename(filename)
    print(f"[DEBUG] 检测文件名: {name}")
    for k, v in DOMAINS.items():
        if k in name:
            print(f"[DEBUG] 匹配到域名: {k} -> {v}")
            return v
    print(f"[DEBUG] 未匹配到特定域名，使用默认: general")
    return "general"


def join_pages(pages: List[str]) -> str:
    return "\n\n".join(pages)


def extract_taxonomy_and_glossary(text: str, source: str, domain: str) -> Dict:
    print(f"[DEBUG] 开始提取分类体系和术语表")
    print(f"[DEBUG] 来源: {source}")
    print(f"[DEBUG] 域名: {domain}")
    print(f"[DEBUG] 文本长度: {len(text)} 字符")

    system = (
        "你是数据分类分级知识层Agent。请基于指南文本提炼领域的分类分级体系和术语表。"
        "仅返回严格JSON，键包含: taxonomy, glossary。"
        "taxonomy需包含四级分类骨架：{levels_definition, tree: List}，不包含items。"
        "tree节点结构: {level1, children:[{level2, children:[{level3, children:[{level4}]}]}]}。"
        "若原文为其他层级结构，请转换并补齐到四级（无法补齐用空字符串）。"
        "glossary为List[{term, definition, synonyms?}]."
        "禁止输出任何非JSON内容。"
        "如果你的输出不是严格 JSON（例如语法错误、缺引号、多余文本），你必须自动立即修复，直到输出合法 JSON 为止。最终输出只能包含修正后的 JSON。"
    )
    user = "来源:" + source + "\n\n" + text

    print(f"[DEBUG] 发送请求到LLM...")
    examples = get_layer1_examples(domain)
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
    obj["taxonomy"]["domain"] = domain
    obj["taxonomy"]["source"] = source

    print(
        f"[DEBUG] 分类体系包含 {len(obj.get('taxonomy', {}).get('categories', []))} 个分类"
    )
    print(f"[DEBUG] 术语表包含 {len(obj.get('glossary', []))} 个术语")

    return obj


def build_seeds(taxonomy: Dict) -> Dict:
    levels = taxonomy.get("levels_definition", [])
    paths: List[Dict] = []

    def walk(node, p):
        if not node:
            return
        if "level1" in node:
            for c2 in node.get("children", []):
                walk(
                    {"level2": c2.get("level2"), "children": c2.get("children", [])},
                    [node.get("level1")],
                )
        elif "level2" in node:
            for c3 in node.get("children", []):
                walk(
                    {"level3": c3.get("level3"), "children": c3.get("children", [])},
                    p + [node.get("level2")],
                )
        elif "level3" in node:
            for c4 in node.get("children", []):
                lvl4 = c4.get("level4")
                paths.append(
                    {
                        "level1": p[0] if len(p) > 0 else "",
                        "level2": p[1] if len(p) > 1 else "",
                        "level3": p[2] if len(p) > 2 else "",
                        "level4": lvl4,
                    }
                )
        else:
            return

    tree = taxonomy.get("tree")
    if isinstance(tree, list):
        for root in tree:
            walk(root, [])
    return {"levels": levels, "paths": paths}


def build_fragments(pages: List[str]) -> List[Dict]:
    frags = []
    for i, p in enumerate(pages, 1):
        frags.append({"page": i, "text": p})
    return frags


def main():
    print(f"[DEBUG] Layer1 主程序开始执行")

    root = os.path.dirname(os.path.dirname(__file__))
    guide_dir = os.path.join(root, "guide")
    print(f"[DEBUG] 指南文件目录: {guide_dir}")

    files = [
        os.path.join(guide_dir, f)
        for f in os.listdir(guide_dir)
        if f.lower().endswith(".pdf")
    ]
    if not files:
        raise RuntimeError("guide 目录下未找到 PDF 指南文件")

    print(
        f"[DEBUG] 找到 {len(files)} 个PDF文件: {[os.path.basename(f) for f in files]}"
    )

    for i, path in enumerate(files, 1):
        print(f"\n[DEBUG] 处理第 {i}/{len(files)} 个文件: {os.path.basename(path)}")

        domain = detect_domain(path)
        print(f"[DEBUG] 读取PDF文件...")
        pages = read_pdf_text(path)
        print(f"[DEBUG] 读取到 {len(pages)} 页")

        text = join_pages(pages)
        print(f"[DEBUG] 合并后文本长度: {len(text)} 字符")

        obj = extract_taxonomy_and_glossary(text, path, domain)
        taxonomy = obj.get("taxonomy", {})
        glossary = obj.get("glossary", [])
        seeds = build_seeds(taxonomy)
        fragments = build_fragments(pages)

        print(f"[DEBUG] 构建了 {len(fragments)} 个文本片段")

        out_dir = os.path.join(root, "artifacts", domain)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0].replace(" ", "_")

        print(f"[DEBUG] 输出目录: {out_dir}")
        print(f"[DEBUG] 基础文件名: {base}")

        print(f"[DEBUG] 保存taxonomy.json...")
        with open(
            os.path.join(out_dir, f"{base}.taxonomy.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(taxonomy, f, ensure_ascii=False, indent=2)

        print(f"[DEBUG] 保存glossary.json...")
        with open(
            os.path.join(out_dir, f"{base}.glossary.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)

        print(f"[DEBUG] 保存taxonomy_seeds.json...")
        with open(
            os.path.join(out_dir, f"{base}.taxonomy_seeds.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(seeds, f, ensure_ascii=False, indent=2)

        print(f"[DEBUG] 保存fragments.json...")
        with open(
            os.path.join(out_dir, f"{base}.fragments.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(fragments, f, ensure_ascii=False, indent=2)

        print(f"[DEBUG] 文件处理完成: {os.path.join(out_dir, f'{base}.taxonomy.json')}")

    print(f"\n[DEBUG] Layer1 主程序执行完成")


if __name__ == "__main__":
    main()
