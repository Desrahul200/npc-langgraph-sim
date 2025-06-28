# agents/quest_completion.py
import re, json
from typing import Dict, Any

with open("quests.json") as f:
    _QUEST_CONFIG = json.load(f)

def quest_completion_node(state: Dict[str, Any]) -> Dict[str, Any]:
    evt = state.get("last_event")
    text = state.get("event_params", {}).get("text", "")
    if evt != "player_chat" or not text:
        return state

    for quest_id in list(state["active_quests"]):
        cfg = _QUEST_CONFIG.get(quest_id, {})
        for pat in cfg.get("complete_triggers", []):
            if re.search(pat, text, re.IGNORECASE):
                # mark complete
                state["active_quests"].remove(quest_id)
                state["completed_quests"].append(quest_id)
                state["response"] = cfg.get("complete_text", "Quest completed!")
                # prevent double‐firing
                state["last_event"]   = None
                state["event_params"] = {}
                print(f"Quest Completion: {quest_id} completed")
                return state
    return state 