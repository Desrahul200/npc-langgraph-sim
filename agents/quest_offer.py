# agents/quest_offer.py

from typing import Dict, Any
import json

with open("quests.json") as f:
    _QUEST_CONFIG = json.load(f)

def quest_offer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    params   = state["tool_action"]["params"]
    quest_id = params["quest_id"]
    offer    = _QUEST_CONFIG[quest_id]["offer_text"]
    # NPC speaks the offer and waits for yes/no
    state["response"]    = offer + " (yes/no?)"
    # clear the tool action so it doesn't loop
    state["tool_action"] = None
    return state 