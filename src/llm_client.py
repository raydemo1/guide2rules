import os
import threading
import time
import random
from zhipuai import ZhipuAI


_MAX = int(os.environ.get("LLM_CONCURRENCY", "2") or "2")
_SEM = threading.Semaphore(max(1, _MAX))

def chat(messages, temperature=0):
    api_key = os.environ.get("GLM_API_KEY") or os.environ.get("ZHIPUAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GLM_API_KEY 环境变量")
    model = os.environ.get("GLM_MODEL", "glm-4.6")
    client = ZhipuAI(api_key=api_key)
    attempts = int(os.environ.get("LLM_RETRY", "6") or "6")
    base = float(os.environ.get("LLM_BACKOFF_SEC", "0.8") or "0.8")
    with _SEM:
        for i in range(max(1, attempts)):
            try:
                resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature)
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
            except Exception as e:
                s = str(e)
                if ("429" in s) or ("1302" in s) or ("并发数过高" in s):
                    time.sleep(base * (2 ** i) + random.random() * 0.25)
                    continue
                if i < attempts - 1:
                    time.sleep(min(1.0, base))
                    continue
                raise
