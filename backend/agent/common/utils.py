# Agent 共用小工具（如从 LLM 文本中提取 JSON）。

import json


def extract_first_json_object(text):
    """
    从文本中提取第一个完整 JSON 对象（以 { 开始、} 结束）。
    供 normalizers、react_runner 等解析 LLM 输出时共用。
    返回 dict 或 None。
    """
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    if "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start:end])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
    return None
