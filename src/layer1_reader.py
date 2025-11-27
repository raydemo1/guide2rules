import json
import os
from typing import Dict, List

from pdf_plumber_text import read_pdf_plumber_text
from convert_to_pdf import convert_docx_to_pdf, convert_doc_to_pdf
from llm_client import chat
from prompt_examples import get_layer1_examples
from domains import detect_domain


def _load_gbt_template() -> str:
    override = os.environ.get("GBT_TEMPLATE_CONFIG") or ""
    root = os.path.dirname(os.path.dirname(__file__))
    cfg_path = (
        override if override else os.path.join(root, "config", "gbt_template.json")
    )
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[DEBUG] 加载初始模板配置: {cfg_path}")
            return json.dumps(data, ensure_ascii=False)
    except Exception:
        return ""


def _load_category_aliases() -> str:
    override = os.environ.get("GBT_CATEGORY_ALIASES") or ""
    root = os.path.dirname(os.path.dirname(__file__))
    cfg_path = (
        override
        if override
        else os.path.join(root, "config", "gbt_category_aliases.json")
    )
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return json.dumps(data, ensure_ascii=False)
    except Exception:
        return ""
    return ""


def _load_domain_overrides(domain: str) -> str:
    override = os.environ.get("DOMAIN_TEMPLATE_OVERRIDES") or ""
    root = os.path.dirname(os.path.dirname(__file__))
    default_path = os.path.join(
        root, "config", "domain_template_overrides", f"{domain}.json"
    )
    cfg_path = override if override else default_path
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return json.dumps(data, ensure_ascii=False)
    except Exception:
        return ""
    return ""


def extract_taxonomy(text: str, source: str, domain: str) -> Dict:
    print(f"[DEBUG] 开始提取分类分级体系")
    print(f"[DEBUG] 来源: {source}")
    print(f"[DEBUG] 域名: {domain}")

    system = (
        "你是数据分类分级知识层 Agent。以输入的模板为骨架组织分类，结合指南文本生成 taxonomy。"
        "等级格式统一为 S+数字（S1/S2…），若存在子级使用 Sx-1、Sx-2…；S1 为最低级，数字越大重要性越高。"
        "【输出键】仅返回严格 JSON，包含: taxonomy。"
        "【taxonomy 要求】顶层为 {levels_definition, tree}；tree 必须遵循模板层级 {level,name,children?,items?}。"
        "1) levels_definition："
        "若某一级包含子级，则使用 Sx-1、Sx-2、Sx-3…；S1 始终代表最低级，数字越大重要性越高；"
        "等级数量由指南文本真实出现的等级数量决定，不得自行增删）。"
        "若指南未提供分级体系，则 levels_definition 返回空数组。"
        "若指南提供分级体系，必须严格按照原文出现顺序逐条提取等级。"
        "若某个等级包含子等级（如“一般数据”下含“一般3级/2级/1级”），则编号为 Sx-1、Sx-2、Sx-3…（顺序依原文）。"
        "每个等级项格式固定为："
        "{code: 'Sx 或 Sx-y', description: '原文定义或空字符串', sublevels: [...] }。"
        "若无子级则去掉sublevels 。"
        "2) tree（如有分类体系）：以初始模板为基础进行填入和扩充，禁止采用指南中的分类框架，允许新增一级/二级分类或删除不相关分支；只在叶子放 items。"
        "节点必须为 {level, name, children?}；不得为缺失层级填充空名称。"
        "【敏感数据与可识别性】仅收录 GB/T 43697-2024 敏感数据；号码/账号/代码类必须给正则；文本型敏感数据需稳定关键词与语义。"
        "items 使用规范名并去重，同义词归一；模板已有 items 不得重复。"
        "【领域扩展/裁剪】若输入提供 domain_extension_hints（如车联网：新增 '车联网业务数据' 一级及其二级），按提示扩展；无关分支可裁剪并在审计记录。"
        "【别名映射】可使用 category_aliases 将原文类别名映射到模板标准名；无法映射时插入最相近父节点。"
        "【输出要求】禁止非 JSON；输出严格合法 JSON。"
    )
    tpl = _load_gbt_template()
    if tpl:
        system = (
            system
            + "【分类模板】请以此模板为骨架组织分类层级；模板已有 items 不要重复；允许在最相近父节点下适度扩展一级/二级/叶子最小项。模板: "
            + tpl
        )

    aliases = _load_category_aliases()
    domain_overrides = _load_domain_overrides(domain)
    payload = {
        "domain": domain,
        "source": source,
        "template": json.loads(tpl) if tpl else {},
        "category_aliases": json.loads(aliases) if aliases else {},
        "domain_extension_hints": (
            json.loads(domain_overrides) if domain_overrides else {}
        ),
        "guide_text": text,
    }

    user = json.dumps(payload, ensure_ascii=False)
    print(f"[DEBUG] 用户请求长度: {len(user)} 字符")
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

    return obj["taxonomy"]


def build_seeds(taxonomy: Dict) -> Dict:
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


def _get_layer1_max_chars() -> int:
    env_val = os.environ.get("LAYER1_MAX_CHARS") or ""
    try:
        v = int(env_val) if env_val else 0
        if v > 0:
            return v
    except Exception:
        pass
    root = os.path.dirname(os.path.dirname(__file__))
    cfg_path = os.path.join(root, "config", "layer1_params.json")
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                v = int(data.get("max_chars", 0) or 0)
                if v > 0:
                    return v
    except Exception:
        pass
    return 200000


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

        out_dir = os.path.join(root, "artifacts", domain)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0].replace(" ", "_")
        text_segs = [
            f.get("text") for f in frags if f.get("type") in ("title", "paragraph")
        ]
        final_text = "\n\n".join([seg for seg in text_segs if seg])
        print(f"[DEBUG] 合并后文本长度: {len(final_text)} 字符")
        max_chars = _get_layer1_max_chars()
        if len(final_text) > max_chars:
            raise RuntimeError("合并文本长度超过200000字符")
        taxonomy = extract_taxonomy(final_text, path, domain)
        seeds = build_seeds(taxonomy)

        print(f"[DEBUG] 保存taxonomy.json...")
        with open(
            os.path.join(out_dir, f"{base}.taxonomy.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(taxonomy, f, ensure_ascii=False, indent=2)

        print(f"[DEBUG] 保存taxonomy_seeds.json...")
        with open(
            os.path.join(out_dir, f"{base}.taxonomy_seeds.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(seeds, f, ensure_ascii=False, indent=2)

        print(f"[DEBUG] 保存fragments.json...")
        with open(
            os.path.join(out_dir, f"{base}.fragments.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(frags, f, ensure_ascii=False, indent=2)

        print(f"[DEBUG] 文件处理完成: {os.path.join(out_dir, f'{base}.taxonomy.json')}")

    print(f"\n[DEBUG] Layer1 主程序执行完成")


if __name__ == "__main__":
    main()
