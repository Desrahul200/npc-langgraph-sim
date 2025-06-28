# agents/quest_response.py

from typing import Dict, Any
import json

with open("quests.json") as f:
    _QUEST_CONFIG = json.load(f)

def quest_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    reply    = state["event_params"]["text"].strip().lower()
    quest_id = state.get("pending_quest")
    config   = _QUEST_CONFIG.get(quest_id, {})
    
    if reply in ("yes", "y"):
        state["active_quests"].append(quest_id)
        state["response"] = config.get("accept_text", "Great, thank you!")
    else:
        state["response"] = config.get("decline_text", "No worries.")
    
    # clear pending and event so we can continue regular flow next tick
    state["pending_quest"] = None
    state["last_event"]    = None
    state["event_params"]  = {}
    return state 