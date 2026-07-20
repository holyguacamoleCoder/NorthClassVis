import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from session.turns import count_user_turns, resolve_loop_turn_count


def test_resolve_turn_from_messages():
    messages = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
    ]
    assert count_user_turns(messages) == 2
    assert resolve_loop_turn_count(messages, stored_user_turn_count=0) == 2


def test_resolve_turn_after_compaction_uses_stored():
    from common.prompts import COMPACT_USER_MESSAGE_PREAMBLE

    messages = [
        {
            "role": "user",
            "content": f"{COMPACT_USER_MESSAGE_PREAMBLE}\n\nsummary",
            "_agent_meta": {"ui_visible": False, "content_kind": "compact_summary"},
        }
    ]
    assert count_user_turns(messages) == 0
    assert resolve_loop_turn_count(messages, stored_user_turn_count=9) == 9


def test_count_user_turns_skips_legacy_compact_preamble():
    from common.prompts import COMPACT_USER_MESSAGE_PREAMBLE

    messages = [
        {"role": "user", "content": f"{COMPACT_USER_MESSAGE_PREAMBLE}\n\nold"},
        {"role": "user", "content": "real question"},
    ]
    assert count_user_turns(messages) == 1
