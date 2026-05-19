"""Shared path constants for the agent runtime."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # NorthClassVision
DATA_DIR = PROJECT_ROOT / "data"
MEMORY_DIR = PROJECT_ROOT / ".memory"
