# main.py

import argparse
import os
import faiss

from persistence import load_state, save_state
from workflows.npc_simulation_graph import build_graph, SimulationState
from agents.player_simulator import player_simulator_node

SAVE_DIR = "savegame"
EMBEDDING_DIMENSION = 384  # must match your memory_synthesizer

def init_fresh_state() -> SimulationState:
    """
    Build a brand-new SimulationState with empty FAISS indices.
    """
    def make_npc_sub(npc_id, personality, inventory):
        idx = faiss.IndexIDMap(faiss.IndexFlatIP(EMBEDDING_DIMENSION))
        return {
            "npc_id":                  npc_id,
            "personality":             personality,
            "emotion_state":           "neutral",
            "inventory":               inventory,
            "memory":                  [],
            "faiss_index":             idx,
            "faiss_id_to_memory_text": {},
            "next_faiss_id":           0,
        }

    # We construct a plain dict and cast it to SimulationState
    state = {
        "player_location":   "Market Plaza",
        "player_inventory":  [],
        "player_stats":      {"gold": 50, "gate_open": False},
        "world_chunks":      {"Market Plaza": {"neighbors": []}},
        "npc_states": {
            "malrik_merchant": make_npc_sub("malrik_merchant", "sharp-eyed merchant", ["spice_pouch"]),
            "helena_guard":    make_npc_sub("helena_guard",    "steadfast town guard",    ["spear","shield"]),
            "rowan_bard":      make_npc_sub("rowan_bard",      "traveling bard",          ["lute","scroll"]),
        },
        "active_quests":    [],
        "completed_quests": [],
        "quest_history":    [],
        "last_event":       None,
        "event_params":     {},
        "tool_action":      None,
        "response":         None,
        "simulation_time":  0,
        "time_of_day":      "morning",
        "weather":          "clear",
        "memory_update":    None,
        "memory_owner":     None,
        "pending_quest":    None,
    }
    return SimulationState(state)  # type: ignore

def main():
    parser = argparse.ArgumentParser(description="Run NPC LangGraph Simulation.")
    parser.add_argument("--input_type", choices=["simulator","user"], default="simulator")
    parser.add_argument("--text",       default="Hello, how's business?",
                        help="If input_type=user, this is what the player says")
    args = parser.parse_args()

    # ── 1) Load or initialize ────────────────────────────────
    if os.path.exists(os.path.join(SAVE_DIR, "state.json")):
        state = load_state(SAVE_DIR)
        print(f"🗄 Loaded saved state from {SAVE_DIR}")
    else:
        state = init_fresh_state()
        print("✨ Starting fresh simulation state")

    # ── 2) Decide what the player says ───────────────────────
    if args.input_type == "simulator":
        sim = player_simulator_node()
        player_text = sim.get("player_input", "")
        print(f"[Simulator] Player says: {player_text}")
    else:
        player_text = args.text
        print(f"[User     ] Player says: {player_text}")

    # ── 3) Seed the event ────────────────────────────────────
    state["last_event"]   = "player_chat"
    state["event_params"] = {"npc_id": "malrik_merchant", "text": player_text}

    # ── 4) Run one tick ──────────────────────────────────────
    graph = build_graph()
    final_state = graph.invoke(state)

    # ── 5) Show the reply ────────────────────────────────────
    print(f"\nNPC (malrik_merchant) replies: {final_state.get('response')}\n")

    # ── 6) Persist everything back ───────────────────────────
    save_state(final_state, SAVE_DIR)
    print(f"💾 Saved state to {SAVE_DIR}")

if __name__ == "__main__":
    main()
