import os
import json


_cache = None


def _load_config() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    root = os.path.dirname(os.path.dirname(__file__))
    override = os.environ.get("DOMAINS_CONFIG") or ""
    cfg_path = override if override else os.path.join(root, "config", "domains.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            _cache = json.load(f)
            print(f"[DEBUG] 载入域配置: {cfg_path}，条目数: {len(_cache)}")
    except Exception as e:
        print(f"[DEBUG] 载入域配置失败: {e}，使用内置默认配置")
        _cache = {
            "金融": "finance",
            "气象": "meteorology",
            "政务": "government",
            "政府": "government",
            "科学": "science",
            "科研": "science",
            "医疗": "healthcare",
            "医疗卫生": "healthcare",
            "教育": "education",
            "交通": "transportation",
            "能源": "energy",
            "环境": "environment",
            "农业": "agriculture",
        }
    return _cache


def detect_domain(filename: str) -> str:
    name = os.path.basename(filename)
    print(f"[DEBUG] 检测文件名: {name}")
    mapping = _load_config()
    for k, v in mapping.items():
        if k in name:
            print(f"[DEBUG] 匹配到域名: {k} -> {v}")
            return v
    print(f"[DEBUG] 未匹配到特定域名，使用默认: general")
    return "general"