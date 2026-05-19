"""
Legacy teaching entry point — implementation moved to common/.

Use:
  from common.system_prompt import SystemPromptBuilder, SystemPromptContext
  from common.memory import MemoryManager, get_memory_manager
"""

from common import prompts
from common.memory import DreamConsolidator, MemoryManager, get_memory_manager
from common.system_prompt import SystemPromptBuilder, SystemPromptContext, get_system_prompt_builder

__all__ = [
    "DreamConsolidator",
    "MemoryManager",
    "SystemPromptBuilder",
    "SystemPromptContext",
    "get_memory_manager",
    "get_system_prompt_builder",
    "prompts",
]
