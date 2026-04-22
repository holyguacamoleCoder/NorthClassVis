# Agent 日志配置集中：agent.llm 的 FileHandler 只在此处初始化，避免多处重复添加。

import logging
from pathlib import Path

# log 目录放在 agent 包下（common 的上一级）
AGENT_LOG_DIR = Path(__file__).resolve().parent.parent / "log"
AGENT_LLM_LOGGER_NAME = "agent.llm"


def ensure_agent_logger():
    """确保 agent.llm logger 已挂载 FileHandler（仅挂一次）。"""
    log = logging.getLogger(AGENT_LLM_LOGGER_NAME)
    if not log.handlers:
        AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(AGENT_LOG_DIR / "agent_llm.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(fh)
    log.setLevel(logging.DEBUG)
    return log
