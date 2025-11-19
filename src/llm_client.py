import os
from zhipuai import ZhipuAI


def chat(messages, temperature=0):
    api_key = os.environ.get("GLM_API_KEY") or os.environ.get("ZHIPUAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GLM_API_KEY 环境变量")
    model = os.environ.get("GLM_MODEL", "glm-4.6")
    client = ZhipuAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model, messages=messages, temperature=temperature
    )
    choices = getattr(resp, "choices", None) or resp.get("choices")
    first = choices[0]
    message = getattr(first, "message", None) or first.get("message")
    content = None
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if not content:
        raise RuntimeError("LLM未返回内容")
    return content
