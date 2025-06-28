import os
import json
from typing import Dict, Any
import faiss

def save_state(state: Dict[str, Any], dir_path: str):
    """
    Dump out:
     - state.json (all primitive fields + NPCSubState without the faiss_index)
     - one .index file per NPC for their FAISS index
    """
    os.makedirs(dir_path, exist_ok=True)

    # 1) Build a JSON‐serializable copy of the state
    serial = {}
    # copy top‐level primitive fields
    for k in (
        "player_location",
        "player_inventory",
        "player_stats",
        "world_chunks",
        "active_quests",
        "completed_quests",
        "quest_history",
        "last_event",
        "event_params",
        "response",
        "simulation_time",
        "time_of_day",
        "weather",
        "pending_quest",
    ):
        serial[k] = state.get(k)

    # copy npc_states without the faiss_index object
    serial["npc_states"] = {}
    for npc_id, npc in state["npc_states"].items():
        serial["npc_states"][npc_id] = {
            "npc_id":                  npc["npc_id"],
            "personality":             npc["personality"],
            "emotion_state":           npc["emotion_state"],
            "inventory":               npc["inventory"],
            "memory":                  npc["memory"],
            "faiss_id_to_memory_text": npc["faiss_id_to_memory_text"],
            "next_faiss_id":           npc["next_faiss_id"],
        }

    # 2) Write state.json
    with open(os.path.join(dir_path, "state.json"), "w") as f:
        json.dump(serial, f, indent=2)

    # 3) Write each NPC's index
    for npc_id, npc in state["npc_states"].items():
        idx = npc.get("faiss_index")
        if idx is not None:
            faiss.write_index(
                idx,
                os.path.join(dir_path, f"{npc_id}.index")
            )


def load_state(dir_path: str) -> Dict[str, Any]:
    """
    Reads state.json + each <npc_id>.index back into a SimulationState dict.
    """
    # 1) Load JSON fields
    with open(os.path.join(dir_path, "state.json")) as f:
        serial = json.load(f)

    # 2) Reconstruct SimulationState skeleton
    state: Dict[str, Any] = {
        k: serial[k] for k in serial if k != "npc_states"
    }
    state["npc_states"] = {}

    # 3) For each NPC in the JSON, rebuild their substate + load FAISS
    for npc_id, npc_j in serial["npc_states"].items():
        # load or init a FAISS index
        idx_file = os.path.join(dir_path, f"{npc_id}.index")
        if os.path.exists(idx_file):
            idx = faiss.read_index(idx_file)
        else:
            # fallback to an empty IP index
            from workflows.npc_simulation_graph import EMBEDDING_DIMENSION
            idx = faiss.IndexIDMap(faiss.IndexFlatIP(EMBEDDING_DIMENSION))

        # Force integer keys for faiss_id_to_memory_text
        mapping = npc_j["faiss_id_to_memory_text"]
        int_mapping = { int(k): v for k, v in mapping.items() }

        state["npc_states"][npc_id] = {
            "npc_id":                  npc_j["npc_id"],
            "personality":             npc_j["personality"],
            "emotion_state":           npc_j["emotion_state"],
            "inventory":               npc_j["inventory"],
            "memory":                  npc_j["memory"],
            "faiss_index":             idx,
            "faiss_id_to_memory_text": int_mapping,
            "next_faiss_id":           npc_j["next_faiss_id"],
        }

    return state 