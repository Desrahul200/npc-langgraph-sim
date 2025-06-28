# agents/event_nodes.py

from typing import Dict, Any

def gossip_node(state):
    print(f"GOSSIP NODE TRIGGERED: {state.get('tool_action')}")
    ta     = state.get("tool_action") or {}
    params = ta.get("params", {})
    target = params.get("target_npc")
    message= params.get("message")

    if target and message and target in state["npc_states"]:
        npc = state["npc_states"][target]
        # 1) Append raw text to the NPC’s memory list
        npc["memory"].append(message)

        # 2) Tell the memory_synthesizer to embed this new chunk
        state["memory_update"] = message
        state["memory_owner"]  = target

    # 3) Clear the action so we don’t re-run
    state["tool_action"] = None
    return state

def player_state_node(state):
    evt    = state.get("last_event")
    params = state.get("event_params", {}) or {}
    ta     = state.get("tool_action") or {}

    if evt == "player_moved":
        dest = params.get("new_location")
        if dest in state["world_chunks"]:
            state["player_location"] = dest

    if ta.get("type") == "give_item":
        item = ta["params"].get("item_id")
        if item:
            state["player_inventory"].append(item)

    if ta.get("type") == "give_gold":
        amt = ta["params"].get("amount", 0)
        state["player_stats"]["gold"] = state["player_stats"].get("gold", 0) + amt

    if ta.get("type") == "open_gate":
        state["player_stats"]["gate_open"] = True

    if ta.get("type") == "repair_item":
        item = ta["params"].get("item_id")
        if item and item in state["player_inventory"]:
            state["player_inventory"].remove(item)
            state["player_inventory"].append(f"repaired_{item}")

    state["tool_action"] = None
    return state
