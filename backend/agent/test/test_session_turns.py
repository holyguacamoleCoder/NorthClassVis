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
    messages = [{"role": "user", "content": "compacted summary"}]
    assert resolve_loop_turn_count(messages, stored_user_turn_count=9) == 9
