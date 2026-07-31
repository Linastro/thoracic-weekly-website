"""严格但带修复的 LLM JSON 解析。

典型修复路径(按优先级):
1. 直接 `json.loads` —— 多数情况下 LLM 输出即为合法 JSON。
2. 移除 ` ̶t̶h̶i̶n̶k̶...̶/̶t̶h̶i̶n̶k̶` 推理块后重试 —— 兼容部分模型把思考过程混入输出。
3. 在剩余文本中扫描,提取第一个平衡的 `{...}` 子串。
4. 仍失败则抛出 `ValueError`,由调用方决定降级策略。
"""

import json
import re

_THINK_BLOCK = re.compile(r"think.*?/think", re.DOTALL)


def parse_strict_json_object(text: str) -> dict:
    """从 LLM 文本中提取第一个 JSON object;带 fallback 修复。"""
    # 1. 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 移除 think.../think 块后重试
    cleaned = _THINK_BLOCK.sub("", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. 提取第一个 {...} 平衡块
    start = cleaned.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    # 4. 抛出
    raise ValueError(f"no JSON object found in: {text[:200]}")
