import argparse
from dotenv import load_dotenv
import os
import json
import numpy as np
import faiss

from workflows.npc_simulation_graph import build_graph # SimulationState no longer directly used here
from agents.player_simulator import player_simulator_node
from utils.print_utils import summarize_for_printing

# Load environment variables from .env file
load_dotenv()

# --- FAISS Configuration ---
FAISS_INDEX_FILE = "npc_faiss.index"
FAISS_MAPPING_FILE = "npc_faiss_mapping.json"
EMBEDDING_DIMENSION = 384  # For all-MiniLM-L6-v2

# Global FAISS components (will be managed within main and passed via graph state)
# faiss_index: faiss.Index | None = None
# faiss_id_to_memory_text: dict[int, str] = {}
# next_faiss_id: int = 0

def initialize_faiss_components():
    """Initializes a new FAISS index and supporting structures, with sim_time = 0."""
    print("Initializing new FAISS components.")
    index_flat = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
    index = faiss.IndexIDMap(index_flat)
    # Now return (index, mapping_dict, next_id, simulation_time)
    return index, {}, 0, 0


def load_faiss_components():
    """
    Loads FAISS index and combined mapping file. The JSON is expected to have:
    {
      "simulation_time": <int>,
      "faiss_mapping": { "<id>": { "text": ..., "npc_id": ..., "timestamp": ... }, ... }
    }
    """
    index = None
    full_mapping = {}
    next_id_val = 0
    sim_time = 0

    try:
        if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(FAISS_MAPPING_FILE):
            print(f"Loading FAISS index from {FAISS_INDEX_FILE}...")
            index = faiss.read_index(FAISS_INDEX_FILE)

            print(f"Loading FAISS mapping + sim_time from {FAISS_MAPPING_FILE}...")
            with open(FAISS_MAPPING_FILE, 'r') as f:
                data = json.load(f)

            # Extract past simulation_time and the nested "faiss_mapping"
            sim_time = data.get("simulation_time", 0)
            id_to_text_mapping_str_keys = data.get("faiss_mapping", {})

            # Convert string keys back to ints
            full_mapping = {
                int(k): v for k, v in id_to_text_mapping_str_keys.items()
            }

            if full_mapping:
                next_id_val = max(full_mapping.keys()) + 1
            else:
                # If mapping is empty but index isn’t, set next_id from index size
                next_id_val = index.ntotal if index else 0
                if next_id_val > 0 and not full_mapping:
                    print("Warning: FAISS index has entries but mapping is empty.")

            print(f"FAISS loaded. Index size: {index.ntotal if index else 0}, Next ID: {next_id_val}, Last sim_time: {sim_time}")
            return index, full_mapping, next_id_val, sim_time

        else:
            print("FAISS files not found. Starting fresh.")
            return None, {}, 0, 0

    except Exception as e:
        print(f"Error loading FAISS components: {e}. Starting fresh.")
        return None, {}, 0, 0


def save_faiss_components(index, id_to_text_mapping, simulation_time):
    """
    Saves the FAISS index to disk, and writes a combined JSON:
      {
         "simulation_time": <int>,
         "faiss_mapping": { "<id>": { "text": ..., "npc_id": ..., "timestamp": ... }, ... }
      }
    """
    if index is None:
        print("FAISS index is None, nothing to save.")
        return

    try:
        print(f"Saving FAISS index to {FAISS_INDEX_FILE} (Size: {index.ntotal})...")
        faiss.write_index(index, FAISS_INDEX_FILE)

        combined = {
            "simulation_time": simulation_time,
            # Convert integer keys back to strings for valid JSON
            "faiss_mapping": { str(k): v for k, v in id_to_text_mapping.items() }
        }
        print(f"Saving combined mapping (incl. sim_time={simulation_time}) to {FAISS_MAPPING_FILE}...")
        with open(FAISS_MAPPING_FILE, 'w') as f:
            json.dump(combined, f, indent=4)
        print("FAISS and simulation_time saved successfully.")
    except Exception as e:
        print(f"Error saving FAISS components: {e}")


def main():
    # Attempt to load FAISS components first
    # Attempt to load FAISS components (and simulation_time) first
    current_faiss_index, current_id_to_memory_text, current_next_faiss_id, current_sim_time = load_faiss_components()

    if current_faiss_index is None:
        current_faiss_index, current_id_to_memory_text, current_next_faiss_id, current_sim_time = initialize_faiss_components()


    parser = argparse.ArgumentParser(description="Run NPC LangGraph Simulation.")
    parser.add_argument(
        "--input_type",
        choices=["user", "simulator"],
        default="simulator",
        help="Choose input type: 'user' for real-time input, 'simulator' for predefined input."
    )
    args = parser.parse_args()

    print("Building NPC simulation graph...")
    npc_app = build_graph()
    print("Graph built successfully.")

    initial_player_input = ""
    if args.input_type == "simulator":
        print("Using player simulator input...")
        player_initial_data = player_simulator_node()
        initial_player_input = player_initial_data["player_input"]
    else:
        print("Using user input.")
        initial_player_input = input("You: ")
    
    initial_graph_input = {
        "player_input": initial_player_input,
        "npc_id": "librarian_001",
        "npc_personality": "a slightly grumpy but knowledgeable old librarian",
        "npc_emotion_state": "neutral",
        "npc_inventory_description": "various old books, a pair of spectacles, and a perpetually refilling cup of tea",
        "passthrough_data": None,
        # Pass FAISS components into the graph state
        "faiss_index": current_faiss_index,
        "faiss_id_to_memory_text": current_id_to_memory_text,
        "next_faiss_id": current_next_faiss_id,
        "simulation_time": current_sim_time,
        "active_quests": [],
        "current_story_beat": None,
        "narrative_cooldown": 0,
        "quest_history": [],
        "tool_action": None,   # ← placeholder, to be filled by CharacterAgent
    }

    print(f"\nStarting simulation with input from {args.input_type} for NPC {initial_graph_input.get('npc_id', '(unknown)')}:\nPlayer: {initial_graph_input['player_input']}")
    
    final_response_output = None
    final_graph_state_for_saving = None 
    
    # Stream events from the graph. Each item in the stream is a dictionary
    # where keys are node names and values are their outputs for that step.
    for event_chunk in npc_app.stream(initial_graph_input):
        print(f"--- Event Chunk ---") 
        # The event_chunk itself can be considered as a snapshot of the state updates at this step.
        # LangGraph typically yields the full state under the "__end__" key in the very last chunk if the graph reached END.
        # Or, the stream just ends, and the accumulated state *is* the final state.
        # Let's print the raw chunk to understand its structure better for our specific graph.
        print(f"Raw Event Chunk Content: {summarize_for_printing(event_chunk)}")

        # Check if this chunk contains the special __end__ marker, whose value is the final state
        if "__end__" in event_chunk and isinstance(event_chunk["__end__"], dict):
            final_graph_state_for_saving = event_chunk["__end__"]
            print(f"Captured final state from __end__ key: {summarize_for_printing(final_graph_state_for_saving)}")
            # Try to get final_response from this definitive final state
            if final_response_output is None and final_graph_state_for_saving.get("dialogue_output", {}).get("final_response"):
                final_response_output = final_graph_state_for_saving["dialogue_output"]
            elif final_response_output is None and final_graph_state_for_saving.get("response"):
                 final_response_output = {"final_response": final_graph_state_for_saving["response"]}
            break # Stop processing chunks once __end__ is found and processed
        else:
            # If no __end__ key, the chunk contains outputs of nodes that just ran.
            # We are interested in the output of dialogue_manager for final_response.
            # And the LATEST state of faiss components which should be in this current chunk if updated.
            # The graph state accumulates, so the last event_chunk *before* the stream ends implicitly IS the final state.
            # So, we always update final_graph_state_for_saving with the current chunk.
            # If the stream ends without an __end__ key, this will be the state used.
            final_graph_state_for_saving = event_chunk

        # Try to extract final_response from any dialogue_manager output in the current chunk
        # This is because dialogue_manager might provide it before the graph formally ends via __end__.
        if "dialogue_manager" in event_chunk:
            dm_output_value = event_chunk["dialogue_manager"]
            if isinstance(dm_output_value, dict) and dm_output_value.get("dialogue_output", {}).get("final_response"):
                 final_response_output = dm_output_value["dialogue_output"]
                 print(f"Captured final_response from dialogue_manager: {summarize_for_printing(final_response_output)}")
                 # If dialogue_manager signals final_response, this effectively means the graph is about to end.
                 # The current event_chunk should be the final state.
                 # Note: This assignment to final_graph_state_for_saving will be overwritten if an __end__ event comes later.

    # After the loop
    print(f"DEBUG: final_graph_state_for_saving for FAISS check: {summarize_for_printing(final_graph_state_for_saving)}")
    
    actual_state_to_save_from = None
    if final_graph_state_for_saving: # final_graph_state_for_saving is the last event_chunk
        if "__end__" in final_graph_state_for_saving and isinstance(final_graph_state_for_saving.get("__end__"), dict):
            actual_state_to_save_from = final_graph_state_for_saving["__end__"]
            print("Retrieved state for saving from '__end__' key in the last event chunk.")
        # If the last chunk is from a specific node (e.g. dialogue_manager) and contains the full state in a nested way
        elif "dialogue_manager" in final_graph_state_for_saving and \
              isinstance(final_graph_state_for_saving.get("dialogue_manager"), dict) and \
              isinstance(final_graph_state_for_saving["dialogue_manager"].get("dialogue_output", {}).get("data"), dict):
            actual_state_to_save_from = final_graph_state_for_saving["dialogue_manager"]["dialogue_output"]["data"]
            print("Retrieved state for saving from dialogue_manager's last output ['dialogue_output']['data'] field.")
        # If the final_graph_state_for_saving (last event chunk) itself is the state dictionary (no node keys)
        # This happens if the graph is simple or the last node directly returns the full state without nesting under its own name.
        # Based on logs, our event_chunks are dicts like {'node_name': output}, so this case is less likely for the *chunk* itself.
        # However, if __end__ is not used, the accumulated state *within* the final node's execution context is what matters.
        # The MemorySynthesizer updated the state, DialogueManager received this updated state in its input_data.
        # So, the input_data of the last DialogueManager execution should be the correct final state.
        # This is already captured by the elif above.
        
        # A simpler assumption: if the stream ends, the latest content of `final_graph_state_for_saving`
        # (which is the last event chunk) must contain the necessary fields if they were correctly propagated.
        # If those fields are top-level in the last event chunk (e.g., from memory_synthesizer output directly becoming the final state)
        elif isinstance(final_graph_state_for_saving, dict) and "faiss_index" in final_graph_state_for_saving: 
            actual_state_to_save_from = final_graph_state_for_saving
            print("Retrieved state for saving directly from the last event chunk (assuming it is the full state).")
        else:
            print("Could not determine the correct nested structure for the final state in the last event chunk.")

    if actual_state_to_save_from and \
       actual_state_to_save_from.get("faiss_index") is not None and \
       actual_state_to_save_from.get("faiss_id_to_memory_text") is not None:
        sim_time_to_save = actual_state_to_save_from.get("simulation_time", current_sim_time)
        print(f"Attempting to save FAISS components and sim_time={sim_time_to_save}. Next ID from state: {actual_state_to_save_from.get('next_faiss_id')}")
        save_faiss_components(
            actual_state_to_save_from["faiss_index"],
            actual_state_to_save_from["faiss_id_to_memory_text"],
            sim_time_to_save
        )

    else:
        print("Warning: Could not retrieve FAISS components from the final graph state to save (actual_state_to_save_from was None or missing keys).")
        if actual_state_to_save_from:
             print(f"Debug: faiss_index in actual_state_to_save_from: {actual_state_to_save_from.get('faiss_index') is not None}")
             print(f"Debug: faiss_id_to_memory_text in actual_state_to_save_from: {actual_state_to_save_from.get('faiss_id_to_memory_text') is not None}")
             print(f"Debug: next_faiss_id in actual_state_to_save_from: {actual_state_to_save_from.get('next_faiss_id')}")

    if final_response_output and final_response_output.get("final_response"):
        print(f"\nNPC: {final_response_output['final_response']}")
    else:
        print("\nSimulation ended, but no final response was captured in the expected format.")

    print("\nSimulation finished.")

if __name__ == "__main__":
    main() 