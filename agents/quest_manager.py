# agents/quest_manager.py

import re, json
from typing import Dict, Any

with open("quests.json") as f:
    _QUEST_CONFIG = json.load(f)

def quest_manager_node(state: Dict[str, Any]) -> Dict[str, Any]:
    active = set(state["active_quests"])
    # if already offered or active, do nothing
    if state.get("pending_quest") or any(q in active for q in _QUEST_CONFIG):
        return state

    # scan for triggers
    for quest_id, info in _QUEST_CONFIG.items():
        if quest_id in active:
            continue
        patterns = [re.compile(p, re.IGNORECASE) for p in info["triggers"]]
        for npc in state["npc_states"].values():
            for mem in npc["memory"]:
                if any(p.search(mem) for p in patterns):
                    # Found a match → *offer* the quest
                    state["tool_action"]   = {
                        "type":   "offer_quest",
                        "params": {"quest_id": quest_id}
                    }
                    state["pending_quest"] = quest_id
                    print(f"Quest Manager: Offering quest {quest_id}")
                    return state
    return state
