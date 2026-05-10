"""
Agent 调试与验收日志：统一命名空间、环境变量开关、可选 JSON 行与文件输出。

环境变量：
- AGENT_LOG_LEVEL：DEBUG / INFO / WARNING / ERROR（默认 INFO）
- AGENT_LOG_JSON：1 / true / yes 时单行 JSON 输出（stderr 与文件共用）
- AGENT_LOG_FILE：追加写入该路径（UTF-8）
- AGENT_LOG_MAX_LEN：字符串/序列化字段截断长度（默认 500）
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

_ROOT_LOGGER_NAME = "northclass.agent"
_DEFAULT_TRUNCATE = 500
_CONFIGURED = False


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _parse_level(name: str) -> int:
    level = getattr(logging, name.upper(), None)
    return level if isinstance(level, int) else logging.INFO


def truncate_for_log(value: Any, max_len: int | None = None) -> str:
    # 截断日志长度
    if max_len is None:
        try:
            max_len = int(os.environ.get("AGENT_LOG_MAX_LEN") or _DEFAULT_TRUNCATE)
        except ValueError:
            max_len = _DEFAULT_TRUNCATE
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        s = json.dumps(value, ensure_ascii=False, default=str)
    else:
        s = str(value)
    if len(s) <= max_len:
        return s
    return s[: max(0, max_len - 3)] + "..."


class _AgentJsonFormatter(logging.Formatter):
    """若日志消息本身是 JSON 对象字符串，则合并 ts/level/logger 后输出一行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        raw = record.getMessage()
        ts = datetime.now(timezone.utc).isoformat()
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                raise ValueError("not a dict")
        except (json.JSONDecodeError, ValueError):
            obj = {"msg": raw}
        obj.setdefault("ts", ts)
        obj["level"] = record.levelname
        obj["logger"] = record.name
        return json.dumps(obj, ensure_ascii=False, default=str)


def configure_from_env() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level = _parse_level(os.environ.get("AGENT_LOG_LEVEL") or "INFO")
    json_mode = _truthy_env("AGENT_LOG_JSON")
    log_file = (os.environ.get("AGENT_LOG_FILE") or "").strip()

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.handlers.clear()
    root.setLevel(level)
    root.propagate = False

    if json_mode:
        fmt: logging.Formatter = _AgentJsonFormatter()
    else:
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(level)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)


def get_logger(component: str) -> logging.Logger:
    configure_from_env()
    suffix = component.strip(".").strip()
    name = _ROOT_LOGGER_NAME if not suffix else f"{_ROOT_LOGGER_NAME}.{suffix}"
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """结构化事件：JSON 模式下消息体为可解析 JSON；否则为人类可读一行。"""
    if _truthy_env("AGENT_LOG_JSON"):
        payload = {"event": event, **fields}
        logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))
    else:
        tail = " | ".join(f"{k}={truncate_for_log(v)}" for k, v in fields.items())
        msg = f"{event} | {tail}" if tail else event
        logger.log(level, "%s", msg)
