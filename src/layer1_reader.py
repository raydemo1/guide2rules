import json
import os
from typing import Dict, List

from pdf_plumber_text import read_pdf_plumber_text
from convert_to_pdf import convert_docx_to_pdf, convert_doc_to_pdf
from llm_client import chat
from prompt_examples import get_layer1_examples
from domains import detect_domain


def join_pages(pages: List[str]) -> str:
    return "\n\n".join(pages)


def extract_taxonomy_and_glossary(text: str, source: str, domain: str) -> Dict:
    print(f"[DEBUG] 开始提取分类体系和术语表")
    print(f"[DEBUG] 来源: {source}")
    print(f"[DEBUG] 域名: {domain}")
    print(f"[DEBUG] 文本长度: {len(text)} 字符")

    system = (
        "你是“数据分类分级知识层 Agent”。请基于指南文本提炼领域的分级体系（如有，级别格式统一为 S+数字，例如 S1、S2、S3…；"
        "若某一级包含子级，则使用 Sx-1、Sx-2、Sx-3…；S1 始终代表最低级，数字越大重要性越高；"
        "等级数量由指南文本真实出现的等级数量决定，不得自行增删）。"
        "并提炼分类体系（如有）与术语表。"
        "仅返回严格 JSON，键包含: taxonomy, glossary。"
        "【taxonomy 要求】"
        "taxonomy 顶层结构必须为：{levels_definition, tree}。"
        "1. 在 levels_definition 中："
        "若指南未提供分级体系，则 levels_definition 返回空数组。"
        "若指南提供分级体系，必须严格按照原文出现顺序逐条提取等级。"
        "若某个等级包含子等级（如“一般数据”下含“一般3级/2级/1级”），则编号为 Sx-1、Sx-2、Sx-3…（顺序依原文）。"
        "每个等级项格式固定为："
        "{code: 'Sx 或 Sx-y', description: '原文定义或空字符串', sublevels: [...] }。"
        "若无子级则去掉sublevels 。"
        "2. tree 表示分类体系（如存在）。"
        "若指南未提供分类体系，则 tree 返回空数组。"
        "若指南提供分类体系："
        "—— 分类层级数量必须与指南文本实际结构一致。"
        "—— 最大层级 = 文本中出现的最深层级。"
        "—— 所有分类路径必须补齐至该最大层级，缺失层级用 name: '' 填补。"
        "—— 每个分类节点格式为：{name: '分类名称或空', children: [...] }。"
        "若指南文本中已经给出最小颗粒度字段（items，例如字段名、字段代码、具体数据项），"
        "则允许在最底层增加 'items': ['item1', 'item2', ...] 字段，用于保留原始字段。"
        "若指南未给出字段名，则不得创建 items。"
        "tree 中除 items 外不得包含示例值或额外属性。"
        "【glossary 要求】"
        "glossary 为 List[{term, definition, synonyms}]。"
        "所有术语必须来自原文；synonyms 若无同义词则必须返回空数组。"
        "【输出要求】"
        "禁止输出任何非 JSON 内容。"
        "最终输出必须是严格合法 JSON。"
        "若输出 JSON 不合法（语法错误、缺少引号、包含多余文本等），必须自动修复并重新输出，直到完全合法为止。"
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

    files = []
    for f in os.listdir(guide_dir):
        fl = f.lower()
        if fl.endswith(".pdf") or fl.endswith(".docx") or fl.endswith(".doc"):
            files.append(os.path.join(guide_dir, f))
    if not files:
        raise RuntimeError("guide 目录下未找到指南文件")

    print(f"[DEBUG] 找到 {len(files)} 个 文件: {[os.path.basename(f) for f in files]}")

    for i, path in enumerate(files, 1):
        print(f"\n[DEBUG] 处理第 {i}/{len(files)} 个文件: {os.path.basename(path)}")

        domain = detect_domain(path)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            print(f"[DEBUG] 读取PDF文件(通过pdfplumber)...")
            frags = read_pdf_plumber_text(path)
        elif ext == ".docx":
            print(f"[DEBUG] 转换DOCX为PDF...")
            pdf_path = convert_docx_to_pdf(path)
            print(f"[DEBUG] 读取转换后的PDF(通过pdfplumber): {pdf_path}")
            frags = read_pdf_plumber_text(pdf_path)
        elif ext == ".doc":
            print(f"[DEBUG] 转换DOC为PDF...")
            pdf_path = convert_doc_to_pdf(path)
            print(f"[DEBUG] 读取转换后的PDF(通过pdfplumber): {pdf_path}")
            frags = read_pdf_plumber_text(pdf_path)
        else:
            raise RuntimeError(f"不支持的文件类型: {ext}")
        print(f"[DEBUG] 读取到 {len(frags)} 段")

        text = join_pages([f["text"] for f in frags])
        print(f"[DEBUG] 合并后文本长度: {len(text)} 字符")

        obj = extract_taxonomy_and_glossary(text, path, domain)
        taxonomy = obj.get("taxonomy", {})
        glossary = obj.get("glossary", [])
        seeds = build_seeds(taxonomy)
        fragments = frags

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
