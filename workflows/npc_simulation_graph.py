from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, Optional, Any, Dict
import operator

# Import agent nodes
from agents.player_simulator import player_simulator_node
from agents.dialogue_manager import dialogue_manager_node
from agents.character_agent import character_agent_node
from agents.memory_synthesizer import memory_synthesizer_node
from agents.world_state import world_state_node
from agents.narrative_director import narrative_director_node

# Define the state for the graph
class SimulationState(TypedDict):
    player_input: str
    response: str
    dialogue_output: Any
    memory_update: str
    # NPC specific attributes - to be populated in main.py or by a future NPC manager
    npc_id: str
    npc_personality: str
    npc_emotion_state: str
    npc_inventory_description: str
    # npc_current_goal: Optional[str] # For future use
    # This field will store the output of the dialogue manager, 
    # which could be a final response or routing information.
    dialogue_output: dict 
    # To carry over data between nodes if necessary, not strictly part of the primary flow fields
    passthrough_data: Any
    simulation_time: int
    time_of_day: str
    location: str
    weather: str
    active_quests: List[str]             # e.g. ["Find the Lost Tome", "Warn Town of Curfew"]
    # What global “beat” is in effect this turn?
    current_story_beat: Optional[str]     # e.g. "curfew_warning", "festival_celebration", "prophecy_whisper"
    # A simple pacing counter so we don’t spam every turn
    narrative_cooldown: int               # number of ticks before next possible injection
    # You could also track “quest_history” if you like, or a boolean to indicate “quest just injected”
    quest_history: List[str]
    # FAISS and memory mapping for vector search
    faiss_index: Any
    faiss_id_to_memory_text: Dict[int, str]
    next_faiss_id: int
    tool_action: Optional[Dict[str, Any]]   # New: engine‐action hook (e.g. give_item, move_to)

def build_graph():
    workflow = StateGraph(SimulationState)

    # Add nodes
    # For the player_simulator, it doesn't take SimulationState as input directly,
    # but its output fits into the state. We'll handle its invocation separately in main.py for now.
    # However, if it were part of a continuous loop within the graph, it would need to conform.
    # For this initial setup, we will consider it as an entry point outside the main looping graph.

    workflow.add_node("dialogue_manager", dialogue_manager_node)
    workflow.add_node("character_agent", character_agent_node)
    workflow.add_node("memory_synthesizer", memory_synthesizer_node)   
    workflow.add_node("world_state", world_state_node)
    workflow.add_node("narrative_director", narrative_director_node)
    # Player simulator is an entry point, not a typical graph node in this flow
    # workflow.add_node("player_simulator", player_simulator_node) # Not added as a conventional node

    # Define edges

    workflow.add_edge("world_state", "narrative_director")
    workflow.add_edge("narrative_director", "dialogue_manager")

    # Conditional routing from dialogue_manager
    def decide_next_node(state: SimulationState):
        dialogue_result = state.get("dialogue_output", {})
        if dialogue_result.get("next_node") == "character_agent":
            return "character_agent"
        elif dialogue_result.get("next_node") == "memory_synthesizer":
            return "memory_synthesizer"
        elif dialogue_result.get("final_response"): # Indicates end of this turn
            return END
        return END # Default to END if no other path

    workflow.add_conditional_edges(
        "dialogue_manager",
        decide_next_node,
        {
            "character_agent": "character_agent",
            "memory_synthesizer": "memory_synthesizer",
            END: END
        }
    )

    workflow.add_edge("character_agent", "dialogue_manager")
    # After memory_synthesizer runs, advance time via world_state, then return to dialogue_manager
    
    workflow.add_edge("memory_synthesizer", "dialogue_manager")
    # Set the entry point for the graph.
    # Since player_simulator is external for now, dialogue_manager is the effective entry point
    # when data comes from the player (either real or simulated).
    workflow.set_entry_point("world_state")


    # Compile the graph
    app = workflow.compile()
    return app

if __name__ == '''__main__''':
    # This is for testing the graph structure directly
    graph = build_graph()
    # To visualize (optional, requires pydot and graphviz)
    # try:
    #     graph.get_graph().draw_mermaid_png(output_file_path="npc_simulation_graph.png")
    #     print("Graph visualized to npc_simulation_graph.png")
    # except Exception as e:
    #     print(f"Could not visualize graph: {e}")

    # Example invocation (simplified, assumes dialogue_manager handles initial input)
    print("Testing graph build...")
    initial_state_from_player = {"player_input": "Hello NPC!", "dialogue_output": {"next_node": "character_agent"}}
    
    # The dialogue_manager expects its own output format to guide routing.
    # For the first call, we simulate that the player input has been processed by an initial routing step
    # (which in a more complex setup might be dialogue_manager itself or an initial input handler).
    # For this structure, the dialogue_manager node is called first with the player input.
    
    inputs = {"player_input": "Test input from player simulator", "dialogue_output": {"next_node": "character_agent"}}
    
    # Correction: The initial input to the graph should be what the entry point node (dialogue_manager) expects.
    # The dialogue_manager_node itself processes the player_input.
    
    first_dm_input = {"player_input": "What is your name?"}

    for event in graph.stream(first_dm_input):
        print(f"Event: {event}")
        # The final output of a run will be the state of the graph when it reaches END
        # The specific output depends on what the last node before END puts into the state.
        # If dialogue_manager is the last node and returns a "final_response", that will be in the state.

    print("\nGraph test complete.")
    # The final result is typically the state of the last node that executed before END.
    # If the graph ends after dialogue_manager provides a final_response, 
    # that response would be accessible in the 'dialogue_output' or a specific response field in the state.
    # For example, if the dialogue_manager puts the final NPC response in a field like 'npc_final_output'
    # then final_result['npc_final_output'] would be it.
    # Based on current dialogue_manager, it stores it in 'final_response' key within 'dialogue_output'.
    # final_result = graph.invoke(first_dm_input)
    # print(f"Final result of test invocation: {final_result}") 