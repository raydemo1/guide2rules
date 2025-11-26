import json
import os
import re
from typing import Dict, List

from pdf_plumber_text import read_pdf_plumber_text
from convert_to_pdf import convert_docx_to_pdf, convert_doc_to_pdf
from llm_client import chat
from prompt_examples import get_layer1_examples
from domains import detect_domain
from layer1_table_parser import build_taxonomy_from_tables, build_pre_extracted_items


def join_pages(pages: List[str]) -> str:
    return "\n\n".join(pages)


def clean_cell_text(s: str) -> str:
    """清理表格单元格内容：去掉换行、多余空格"""
    return re.sub(r"\s+", " ", s or "").strip()


def extract_taxonomy_and_glossary(text: str, source: str, domain: str) -> Dict:
    print(f"[DEBUG] 开始提取分类体系和术语表")
    print(f"[DEBUG] 来源: {source}")
    print(f"[DEBUG] 域名: {domain}")

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
        "—— 分类层级数量必须与指南文本实际结构一致，可为任意深度。"
        "—— 不得强制补齐到最深层级；不得为缺失层级填充空名称。"
        "—— 每个分类节点必须包含 {level: 数字, name: 名称, children: [...]}；level 从 1 开始逐级递增，深度不限。"
        "—— 节点结构示例：{level:1, name:'基础设施', children:[ {level:2, name:'公路交通基础设施', children:[ ... ]} ]}。"
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


def validate_taxonomy_with_llm(taxonomy: Dict, source: str, domain: str) -> Dict:
    print(f"[DEBUG] 使用LLM校验并修复taxonomy结构")
    system = (
        "你是JSON结构校验与修复Agent。"
        "输入包含taxonomy对象，可能存在层级缺失、键不规范或结构不一致。"
        "请输出严格合法的JSON，仅包含: {taxonomy}，其中 taxonomy 顶层为 {levels_definition, tree}。"
        "tree 节点必须统一为 {level: 数字>=1, name: 字符串, children: [可选]} 格式，深度不限；"
        "若children不存在则去掉该键；禁止添加输入未出现的分类名称；仅允许修复结构，不得补齐空名称或强行填充缺失层级。"
        "levels_definition 若不存在则返回空数组。"
        "禁止输出任何非JSON内容。"
    )
    user = json.dumps(
        {"domain": domain, "source": source, "taxonomy": taxonomy}, ensure_ascii=False
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content = chat(messages)
    s = content.find("{")
    e = content.rfind("}")
    if s == -1 or e == -1:
        print("[DEBUG] LLM未返回JSON，使用原taxonomy")
        return taxonomy
    json_str = content[s : e + 1]
    try:
        obj = json.loads(json_str)
        fixed = obj.get("taxonomy") or taxonomy
        return fixed
    except Exception:
        print("[DEBUG] 校验解析失败，使用原taxonomy")
        return taxonomy


def build_seeds(taxonomy: Dict, fragments: List[Dict]) -> Dict:
    levels = taxonomy.get("levels_definition", [])

    def node_name(node: Dict) -> str:
        if "name" in node:
            return str(node.get("name") or "").strip()
        for k in sorted(node.keys()):
            if k.startswith("level"):
                return str(node.get(k) or "").strip()
        return ""

    path_items: List[Dict] = []

    def walk(node: Dict, acc: List[str]):
        nm = node_name(node)
        cur = acc + ([nm] if nm else [])
        children = node.get("children") or []
        if children:
            for ch in children:
                walk(ch, cur)
        else:
            if cur:
                items = []
                if isinstance(node.get("items"), list):
                    items = [
                        str(x or "").strip()
                        for x in node.get("items")
                        if str(x or "").strip()
                    ]
                path_items.append({"path": cur, "items": items})

    tree = taxonomy.get("tree")
    if isinstance(tree, list):
        for root in tree:
            walk(root, [])

    return {"levels": levels, "paths": path_items}


def main():
    print(f"[DEBUG] Layer1 主程序开始执行")

    root = os.path.dirname(os.path.dirname(__file__))
    guide_dir = os.path.join(root, "guide")
    tmp_dir = os.path.join(root, "artifacts", "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
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
            pdf_path = convert_docx_to_pdf(path, tmp_dir)
            print(f"[DEBUG] 读取转换后的PDF(通过pdfplumber): {pdf_path}")
            try:
                frags = read_pdf_plumber_text(pdf_path)
            finally:
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass
        elif ext == ".doc":
            print(f"[DEBUG] 转换DOC为PDF...")
            pdf_path = convert_doc_to_pdf(path, tmp_dir)
            print(f"[DEBUG] 读取转换后的PDF(通过pdfplumber): {pdf_path}")
            try:
                frags = read_pdf_plumber_text(pdf_path)
            finally:
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass
        else:
            raise RuntimeError(f"不支持的文件类型: {ext}")
        print(f"[DEBUG] 读取到 {len(frags)} 段")

        # 构建 fragments：保留结构化表格和原始标题/段落
        fragments: List[Dict] = []
        for f in frags:
            if f.get("type") == "table":
                headers = f.get("rows", [])[:1]
                data_rows = f.get("rows", [])[1:] if f.get("rows") else []
                fragments.append(
                    {
                        "type": "table",
                        "page": f.get("page", 0),
                        "headers": headers[0] if headers else [],
                        "rows": data_rows,
                        "fields": f.get("fields", []),
                    }
                )
            else:
                t = re.sub(r"\s+", " ", f.get("text") or "").strip()
                if t:
                    fragments.append(
                        {
                            "type": f.get("type"),
                            "text": t,
                            "level": f.get("level", ""),
                            "page": f.get("page", 0),
                        }
                    )

        # 先尝试基于表格直接解析，成功则跳过 LLM 与文本拼接
        parsed = build_taxonomy_from_tables(frags)
        pre_items = build_pre_extracted_items(
            frags, domain, os.path.join("guide", os.path.basename(path))
        )
        out_dir = os.path.join(root, "artifacts", domain)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0].replace(" ", "_")
        if pre_items.get("extraction"):
            taxonomy = validate_taxonomy_with_llm(
                parsed, os.path.join("guide", os.path.basename(path)), domain
            )
            glossary = []
            print(f"[DEBUG] 直接使用表格解析的预抽取items，跳过LLM")
            with open(
                os.path.join(out_dir, f"{base}.items.pre_extracted.json"),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(pre_items, f, ensure_ascii=False, indent=2)
            # 保存结构化表格以便审计
            tables_only = [frag for frag in fragments if frag.get("type") == "table"]
            with open(
                os.path.join(out_dir, f"{base}.tables.json"), "w", encoding="utf-8"
            ) as f:
                json.dump({"tables": tables_only}, f, ensure_ascii=False, indent=2)
        else:
            text_segs = [
                frag.get("text")
                for frag in fragments
                if frag.get("type") in ("title", "paragraph")
            ]
            final_text = "\n\n".join([seg for seg in text_segs if seg])
            print(f"[DEBUG] 合并后文本长度: {len(final_text)} 字符")
            obj = extract_taxonomy_and_glossary(final_text, path, domain)
            taxonomy = obj.get("taxonomy", {})
            glossary = obj.get("glossary", [])
        seeds = build_seeds(taxonomy, fragments)

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
