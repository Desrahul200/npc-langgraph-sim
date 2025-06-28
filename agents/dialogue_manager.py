# Description: Manages the flow of dialogue, deciding which agent to call next.
from typing import TypedDict, Annotated, Union, Dict, Any, TYPE_CHECKING
from langgraph.graph.message import add_messages
# from workflows.npc_simulation_graph import SimulationState # For type hinting
from utils.print_utils import summarize_for_printing

if TYPE_CHECKING:
    from workflows.npc_simulation_graph import SimulationState # For type hinting

class DialogueManagerAgent:
    def __init__(self):
        # Potentially initialize LLM client here if needed for more complex routing
        pass

    def run_dialogue_manager(self, input_data: 'SimulationState') -> dict:
        print(f"Dialogue Manager received: {summarize_for_printing(input_data, keys_to_redact=['faiss_index'])}")

        # grab the latest player utterance from event_params
        player_input = input_data.get("event_params", {}).get("text")
        npc_response_content = input_data.get("response") # From CharacterAgent
        memory_update_content = input_data.get("memory_update") # From MemorySynthesizer

        # Prepare a dictionary of the current state to pass through, excluding previous dialogue_output
        passthrough_state_data = {k: v for k, v in input_data.items() if k != "dialogue_output"}

        if memory_update_content or \
           (player_input is None or (isinstance(player_input, str) and player_input.strip().lower() in ["quit", "exit"])):
            final_npc_response = npc_response_content if npc_response_content else "The librarian nods silently."
            print(f"Dialogue Manager: Ending interaction. Final response: {final_npc_response}")
            return {
                "dialogue_output": {
                    "final_response": final_npc_response,
                    "data": passthrough_state_data
                }
            }

        if npc_response_content and not memory_update_content:
            next_node = "memory_synthesizer"
            print("Dialogue Manager: Routing to Memory Synthesizer.")
        elif player_input and not npc_response_content:
            next_node = "character_agent"
            print("Dialogue Manager: Routing to Character Agent.")
        else:
            print("Dialogue Manager: Unexpected state, ending interaction.")
            return {
                "dialogue_output": {
                    "final_response": npc_response_content if npc_response_content else "The librarian seems unsure how to proceed.",
                    "data": passthrough_state_data
                }
            }
            
        return {
            "dialogue_output": {
                "next_node": next_node,
                "data": passthrough_state_data
            }
        }

# Node function for LangGraph
def dialogue_manager_node(input_data: 'SimulationState') -> dict:
    if not isinstance(input_data, dict):
        print(f"Error: dialogue_manager_node received input that is not a dict: {type(input_data)}")
        return {"dialogue_output": {"error": "Invalid input to dialogue manager", "original_input": input_data}}
    
    manager = DialogueManagerAgent()
    return manager.run_dialogue_manager(input_data)

# Example of how to use the agent (typically called by LangGraph)
if __name__ == '__main__':
    # This import is fine here as it's not part of the main app's import cycle
    from workflows.npc_simulation_graph import SimulationState
    manager = DialogueManagerAgent()
    
    sample_input_from_player: SimulationState = {
        "player_input": "Hello, I'm looking for a book on dragons.",
        "npc_id": "librarian_001",
        "npc_personality": "grumpy",
        "npc_emotion_state": "neutral",
        "npc_inventory_description": "books",
        "faiss_index": None, 
        "faiss_id_to_memory_text": {}, 
        "next_faiss_id": 0,
        "response": "", # Ensure all keys of SimulationState are present
        "memory_update": "",
        "dialogue_output": {},
        "passthrough_data": None
    }
    output1 = manager.run_dialogue_manager(sample_input_from_player)
    print(f"Output 1: {summarize_for_printing(output1)}")

    # Ensure sample_input_from_character also conforms to SimulationState
    dialogue_output_from_1 = output1.get("dialogue_output", {})
    data_from_1 = dialogue_output_from_1.get("data", sample_input_from_player) # Use initial if data not present
    
    sample_input_from_character: SimulationState = {
        **data_from_1, # type: ignore
        "response": "The librarian grunts, 'Dragons, eh? Section 7B, mind the dust.'",
        "npc_emotion_state": "annoyed", 
        "dialogue_output": dialogue_output_from_1, 
    }
    # Ensure all keys are present, even if some are just defaults from the previous state
    for key in SimulationState.__annotations__.keys():
        if key not in sample_input_from_character:
            sample_input_from_character[key] = data_from_1.get(key) # type: ignore
            
    output2 = manager.run_dialogue_manager(sample_input_from_character)
    print(f"Output 2: {summarize_for_printing(output2)}")

    dialogue_output_from_2 = output2.get("dialogue_output", {})
    data_from_2 = dialogue_output_from_2.get("data", sample_input_from_character)

    sample_input_from_memory: SimulationState = {
        **data_from_2, # type: ignore
        "memory_update": "Player asked for dragon books, librarian directed to 7B.",
        "faiss_id_to_memory_text": {"0": {"text":"Player asked for dragon books...", "npc_id":"librarian_001"}}, 
        "next_faiss_id": 1,
        "dialogue_output": dialogue_output_from_2,
    }
    for key in SimulationState.__annotations__.keys():
        if key not in sample_input_from_memory:
            sample_input_from_memory[key] = data_from_2.get(key) # type: ignore

    output3 = manager.run_dialogue_manager(sample_input_from_memory)
    print(f"Output 3: {summarize_for_printing(output3)}")

    sample_input_quit: SimulationState = {
        "player_input": "quit",
        "npc_id": "librarian_001",
        "faiss_index": None, 
        "faiss_id_to_memory_text": {}, 
        "next_faiss_id": 1,
        "response": "",
        "memory_update": "",
        "dialogue_output": {},
        "npc_personality": "grumpy",
        "npc_emotion_state": "neutral",
        "npc_inventory_description": "books",
        "passthrough_data": None
    }
    output4 = manager.run_dialogue_manager(sample_input_quit)
    print(f"Output 4: {summarize_for_printing(output4)}") 