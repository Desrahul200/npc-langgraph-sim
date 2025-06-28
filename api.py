# api.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict
import os

import faiss
from persistence import load_state, save_state
from workflows.npc_simulation_graph import build_graph, SimulationState
from agents.player_simulator import player_simulator_node
from main import init_fresh_state, SAVE_DIR  # <-- pull in your init_fresh_state & SAVE_DIR

app = FastAPI(
    title="NPC Simulation API",
    description="Expose /load, /tick, /save for your Unreal/Unity client"
)

# Build your graph once
graph = build_graph()

# In-memory state
sim_state: SimulationState

# Keys to include in the JSON payload
_TOP_FIELDS = [
    "player_location","player_inventory","player_stats",
    "world_chunks","active_quests","completed_quests","quest_history",
    "last_event","event_params","response","simulation_time",
    "time_of_day","weather","pending_quest"
]
_NPC_FIELDS = [
    "npc_id","personality","emotion_state","inventory",
    "memory","faiss_id_to_memory_text","next_faiss_id"
]

def _serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in _TOP_FIELDS:
        out[k] = state.get(k)
    out["npc_states"] = {}
    for npc_id, npc in state["npc_states"].items():
        sub = { f: npc.get(f) for f in _NPC_FIELDS }
        out["npc_states"][npc_id] = sub
    return out

@app.on_event("startup")
def _startup():
    global sim_state
    # Load if we have a save on disk, otherwise brand-new
    save_json = os.path.join(SAVE_DIR, "state.json")
    if os.path.exists(save_json):
        sim_state = load_state(SAVE_DIR)
        print(f"🗄  Loaded saved state from {SAVE_DIR}")
    else:
        sim_state = init_fresh_state()
        print("✨ Starting fresh simulation state")

class TickRequest(BaseModel):
    event: str
    params: Dict[str, Any] = {}

@app.post("/load")
def load_endpoint():
    """ Return the current sim state (JSON-safe). """
    return {"state": _serialize_state(sim_state)}

@app.post("/tick")
def tick(req: TickRequest):
    """ Advance one tick with the given event/params. """
    global sim_state
    sim_state["last_event"]   = req.event
    sim_state["event_params"] = req.params
    sim_state = graph.invoke(sim_state)
    save_state(sim_state, SAVE_DIR)
    return {"state": _serialize_state(sim_state)}

@app.post("/save")
def save_endpoint():
    """ Force a save now. """
    save_state(sim_state, SAVE_DIR)
    return {"status": "ok"}
