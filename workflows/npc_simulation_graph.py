# workflows/npc_simulation_graph.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional, Any, Dict
import numpy as np

# Import agent nodes
from agents.player_simulator import player_simulator_node
from agents.dialogue_manager import dialogue_manager_node
from agents.character_agent import character_agent_node
from agents.memory_synthesizer import memory_synthesizer_node
from agents.world_state import world_state_node
from agents.narrative_director import narrative_director_node
from agents.event_nodes import gossip_node, player_state_node
from agents.quest_manager import quest_manager_node
from agents.quest_offer import quest_offer_node
from agents.quest_response import quest_response_node
from agents.quest_completion import quest_completion_node

class NPCSubState(TypedDict):
    npc_id: str
    personality: str
    emotion_state: str
    inventory: List[str]
    memory: List[str]
    faiss_index: Any
    faiss_id_to_memory_text: Dict[int, str]
    next_faiss_id: int

class SimulationState(TypedDict):
    # Player State
    player_location: str
    player_inventory: List[str]
    player_stats: Dict[str, Any]

    # World Model (just Market Plaza)
    world_chunks: Dict[str, Dict[str, Any]]

    # Per-NPC states
    npc_states: Dict[str, NPCSubState]

    # (Optional) Quests & history
    active_quests: List[str]
    completed_quests: List[str]
    quest_history: List[str]

    # Event routing hooks
    last_event: Optional[str]
    event_params: Dict[str, Any]
    tool_action: Optional[Dict[str, Any]]
    response: Optional[str]
    # Persistent world clock
    simulation_time: int
    time_of_day: str
    weather: str
    memory_update: Optional[str]
    memory_owner:  Optional[str]
    pending_quest: Optional[str]

def event_router_node(state: SimulationState) -> SimulationState:
    # Once we've seen a player event, consume it so it doesn't repeat forever
    # (we'll clear both last_event and event_params immediately)
    return state

def clear_event_node(state: SimulationState) -> SimulationState:
    state["last_event"]    = None
    state["event_params"]  = {}
    state["memory_update"] = None
    state["tool_action"]   = None
    
    return state


def decide_next_node(state: SimulationState) -> str:
    evt        = state.get("last_event")
    ta         = state.get("tool_action") or {}
    pending    = state.get("pending_quest")

    # 1) If a new quest was just spawned → offer it
    if ta.get("type") == "offer_quest":
        return "quest_offer"

    # 2) If we're awaiting a yes/no on a pending offer…
    if pending and evt == "player_chat":
        return "quest_response"

    # 3) Every player_chat should first go through the completion checker
    #    (it will only mark something complete if it matches one of your complete_triggers)
    if evt == "player_chat" and state.get("active_quests"):
        return "quest_completion"

    # 4) …then fall back into your normal flow
    if evt in ("player_chat","player_near_npc"):
        return "character_agent"
    if ta.get("type") == "gossip":
        return "gossip_node"
    if evt == "player_moved" or ta.get("type") in (
        "give_item", "give_gold", "open_gate", "repair_item"
    ):
        return "player_state"
    return END

def build_graph():
    workflow = StateGraph(SimulationState)

    # 1) Entry point router
    workflow.add_node("event_router",    event_router_node)
    workflow.add_node("clear_event",     clear_event_node)
    # 2) Core agents
    workflow.add_node("dialogue_manager",   dialogue_manager_node)
    workflow.add_node("character_agent",    character_agent_node)
    workflow.add_node("memory_synthesizer", memory_synthesizer_node)
    workflow.add_node("world_state",        world_state_node)
    workflow.add_node("narrative_director", narrative_director_node)
    workflow.add_node("quest_manager",      quest_manager_node)
    workflow.add_node("quest_offer",        quest_offer_node)
    workflow.add_node("quest_response",     quest_response_node)
    workflow.add_node("quest_completion",   quest_completion_node)

    # 3) New nodes for gossip & player updates
    workflow.add_node("gossip_node",    gossip_node)
    workflow.add_node("player_state",   player_state_node)

    # 4) Conditional routing off the router
    workflow.add_conditional_edges(
        "event_router",
        decide_next_node,
        {
            "character_agent": "character_agent",
            "gossip_node":     "gossip_node",
            "player_state":    "player_state",
            "quest_offer":     "quest_offer",
            "quest_response":  "quest_response",
            "quest_completion": "quest_completion",
            END:               END
        }
    )

    # 5) Core event-driven flow
    #    If character_agent emitted a gossip action, route to gossip_node,
    #    otherwise go straight to memory_synthesizer.
    def after_character(state: SimulationState) -> str:
        ta = state.get("tool_action") or {}
        if ta.get("type") == "gossip":
            return "gossip_node"
        return "memory_synthesizer"

    workflow.add_conditional_edges(
        "character_agent",
        after_character,
        {
            "gossip_node":        "gossip_node",
            "memory_synthesizer": "memory_synthesizer"
        }
    )

    workflow.add_edge("memory_synthesizer", "world_state")
    # ── 1) Inject world events / quest logic ──────────────
    workflow.add_edge("world_state",        "narrative_director")
    # ── 2) Hand off to quest manager for quest tracking ─
    workflow.add_edge("narrative_director", "quest_manager")
    # ── 3) Route based on quest state ─
    workflow.add_conditional_edges(
        "quest_manager",
        decide_next_node,
        {
            "quest_offer":     "quest_offer",
            "quest_response":  "quest_response",
            "quest_completion": "quest_completion",
            "character_agent": "character_agent",
            "gossip_node":     "gossip_node",
            "player_state":    "player_state",
            END:               END
        }
    )
    # ── 4) Once dialogue manager says "done" (or picks next), clear & loop ─
    workflow.add_edge("quest_completion",   "dialogue_manager")
    workflow.add_edge("dialogue_manager",   "clear_event")
    workflow.add_edge("clear_event",        "event_router")
    # 6) Gossip still goes into memory synthesizer (then world_state → narrative → quest → dialogue → …)
    workflow.add_edge("gossip_node",         "memory_synthesizer")

    # 7) Player-state flow
    workflow.add_edge("player_state",        "world_state")

    # 8) Quest flow
    workflow.add_edge("quest_offer",     "clear_event")
    workflow.add_edge("quest_response",  "clear_event")
    workflow.add_edge("quest_completion","clear_event")

    # 9) Set the entry point to the router
    workflow.set_entry_point("event_router")

    return workflow.compile()

if __name__ == "__main__":
    # Build the graph
    graph = build_graph()

    # Create a minimal initial state
    state: SimulationState = {
        "player_location":   "Market Plaza",
        "player_inventory":  [],
        "player_stats":      {"gold": 50, "gate_open": False},
        "world_chunks":      {"Market Plaza": {"neighbors": []}},
        "npc_states": {
            "malrik_merchant": {
                "npc_id":                  "malrik_merchant",
                "personality":             "sharp-eyed merchant",
                "emotion_state":           "neutral",
                "inventory":               ["spice_pouch"],
                "memory":                  [],
                "faiss_index":             None,
                "faiss_id_to_memory_text": {},
                "next_faiss_id":           0
            },
            # (define helena_guard and rowan_bard similarly if you like)
        },
        "active_quests":    [],
        "completed_quests": [],
        "quest_history":    [],
        "last_event":       None,
        "event_params":     {},
        "tool_action":      None,
        "response":         None,     # ← add this line
        "simulation_time":  0,
        "time_of_day":      "morning",
        "weather":          "clear",
        "pending_quest":    None,
    }

    # Fire a player_chat event toward Malrik
    state["last_event"]   = "player_chat"
    state["event_params"] = {"npc_id": "malrik_merchant", "text": "Hello, how's business?"}

    # Run one tick
    final_state = graph.invoke(state)

    # Inspect what happened
    print("Response:   ", final_state.get("response"))
    print("Emotion:    ", final_state["npc_states"]["malrik_merchant"]["emotion_state"])
    print("Tool action:", final_state.get("tool_action"))
    print("Memory:     ", final_state["npc_states"]["malrik_merchant"]["memory"])
