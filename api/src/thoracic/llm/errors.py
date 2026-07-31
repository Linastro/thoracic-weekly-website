"""LLM 客户端异常类。"""


class LlmError(Exception):
    """所有 LLM 错误的基类。"""


class LlmAuthError(LlmError):
    """401 / 403:API Key 缺失或无效。不建议重试。"""


class LlmRateLimitError(LlmError):
    """429:请求频率超限。可按指数退避重试。"""


class LlmServerError(LlmError):
    """5xx:上游服务端错误。可按指数退避重试。"""


class LlmJsonParseError(LlmError):
    """LLM 响应不是合法 JSON,或结构与 OpenAI chat.completions 不一致。"""
