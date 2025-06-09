import os
from groq import Groq
from sentence_transformers import SentenceTransformer
from utils.print_utils import summarize_for_printing
import numpy as np # Ensure numpy is imported
import faiss # Ensure faiss is imported (though not directly used in type hints here)

# Constants for FAISS (embedding dimension should match main.py)
EMBEDDING_DIMENSION = 384

# Attempt to import the shared long-term memory store from main.py
# This creates a dependency on main.py being in the Python path, which is typical when running from project root.
# try:
#     from main import npc_long_term_memory
# except ImportError:
#     print("Warning: Could not import npc_long_term_memory from main.py. Long-term memory will not persist across calls in this context.")
#     npc_long_term_memory = {} # Local fallback if import fails (e.g., during isolated testing of the agent)

# Initialize SentenceTransformer model
# This will download the model on first run if not cached.
# Using a relatively small and fast model.
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    SENTENCE_TRANSFORMER_AVAILABLE = True
    print("SentenceTransformer model loaded successfully for MemorySynthesizer.") # Clarified agent name
except Exception as e:
    print(f"Warning: Could not load SentenceTransformer model for MemorySynthesizer: {e}. Semantic embeddings will not be generated.")
    embedding_model = None
    SENTENCE_TRANSFORMER_AVAILABLE = False

# Initialize Groq Client
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    GROQ_API_KEY_AVAILABLE = True
except Exception as e:
    print(f"Warning: Groq API key not found or client could not be initialized for MemorySynthesizer: {e}")
    client = None
    GROQ_API_KEY_AVAILABLE = False

def memory_synthesizer_node(input_data):
    # print(f"Memory Synthesizer received (summary): {input_summary}") # Old print
    print(f"Memory Synthesizer received: {summarize_for_printing(input_data, keys_to_redact=['faiss_index'])}")

    player_input = input_data.get("player_input", "(no player input recorded)")
    npc_response = input_data.get("response", "(no NPC response recorded)")
    npc_id = input_data.get("npc_id", "unknown_npc")

    # --- Get FAISS components from input_data ---
    faiss_index = input_data.get("faiss_index")
    faiss_id_to_memory_text = input_data.get("faiss_id_to_memory_text", {})
    current_next_faiss_id = input_data.get("next_faiss_id", 0)
    current_time = input_data.get("simulation_time", 0)
    if faiss_index is None:
        print(f"Warning: MemorySynthesizer ({npc_id}) did not receive a FAISS index. Memory will not be saved to FAISS.")
        # Fallback behavior: still generate summary but don't save to FAISS
        # or potentially re-initialize a temporary one if that's desired (not done here)

    # Default memory update if LLM call is not possible or fails
    memory_update_text = f"Interaction occurred: Player said '{player_input}', NPC {npc_id} responded '{npc_response}'. (Fallback memory)"
    updated_faiss_components = {
        "faiss_index": faiss_index,
        "faiss_id_to_memory_text": faiss_id_to_memory_text,
        "next_faiss_id": current_next_faiss_id
    }

    if not GROQ_API_KEY_AVAILABLE or not client:
        print(f"Memory Synthesizer ({npc_id}): Groq API key/client not available. Returning fallback memory.")
        return {"memory_update": memory_update_text, **updated_faiss_components} # Return FAISS components even on fallback

    if player_input == "(no player input recorded)" and npc_response == "(no NPC response recorded)":
        memory_update_text = "No specific interaction details to summarize. (Fallback memory)"
        return {"memory_update": memory_update_text, **updated_faiss_components}

    # --- Construct Prompt for LLM to summarize the interaction ---
    # The goal is a concise memory entry from the NPC's perspective.
    system_prompt = (
        f"You are a memory synthesis module for an NPC named {npc_id}. "
        f"Your task is to create a brief, third-person memory entry summarizing an interaction. "
        f"Focus on the key information exchanged or events that occurred. Start the memory with '{npc_id} remembers that...' or similar. Example: '{npc_id} remembers that the player asked about the weather, and {npc_id} mentioned it looked like rain.'"
    )

    interaction_to_summarize = f"Player said: \"{player_input}\"\n{npc_id} (NPC) responded: \"{npc_response}\""

    user_prompt = f"Summarize the following interaction into a concise memory entry for {npc_id}:\n\n{interaction_to_summarize}"

    try:
        print(f"Memory Synthesizer ({npc_id}): Sending prompt to Groq Llama3 to summarize interaction...")
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="llama3-8b-8192", # Using a smaller model for summarization
            temperature=0.5, max_tokens=100, top_p=0.9,
        )
        llm_summary = chat_completion.choices[0].message.content.strip()
        if llm_summary:
            memory_update_text = llm_summary
        else:
            memory_update_text = f"{npc_id} noted an interaction occurred but no specific summary was generated. (LLM returned empty)"
        print(f"Memory Synthesizer ({npc_id}): Received summary from Groq: {memory_update_text}")

        memory_embedding_vector = None
        if SENTENCE_TRANSFORMER_AVAILABLE and embedding_model:
            try:
                # Encode returns a numpy array, ensure it's 2D for FAISS (1, EMBEDDING_DIMENSION)
                raw_embedding = embedding_model.encode(memory_update_text, convert_to_numpy=True)
                if raw_embedding.ndim == 1:
                    memory_embedding_vector = np.expand_dims(raw_embedding, axis=0)
                else:
                    memory_embedding_vector = raw_embedding
                # Ensure it's float32, as FAISS often expects this
                memory_embedding_vector = memory_embedding_vector.astype('float32')
                norms = np.linalg.norm(memory_embedding_vector, axis=1, keepdims=True)
                norms[norms == 0] = 1e-12
                memory_embedding_vector = memory_embedding_vector / norms 
                print(f"Memory Synthesizer ({npc_id}): Generated embedding for summary (shape: {memory_embedding_vector.shape}).")
            except Exception as e:
                print(f"Memory Synthesizer ({npc_id}): Error generating embedding: {e}")

        # --- Save to FAISS --- 
        if faiss_index is not None and memory_embedding_vector is not None and npc_id != "unknown_npc":
            try:
                # The ID for FAISS will be the current `next_faiss_id` (which is effectively the count before adding)
                faiss_id_to_add = np.array([current_next_faiss_id], dtype='int64')
                faiss_index.add_with_ids(memory_embedding_vector, faiss_id_to_add)
                
                # Store the text separately, mapping our new FAISS ID to the text and originating NPC
                # The mapping key should be the ID we just used.
                faiss_id_to_memory_text[current_next_faiss_id] = {
                    "text": memory_update_text,
                    "npc_id": npc_id, # Store npc_id for potential multi-NPC scenarios
                    "timestamp": current_time
                }
                
                new_next_faiss_id = current_next_faiss_id + 1 # Increment for the next addition
                updated_faiss_components["faiss_index"] = faiss_index # Index is modified in-place
                updated_faiss_components["faiss_id_to_memory_text"] = faiss_id_to_memory_text
                updated_faiss_components["next_faiss_id"] = new_next_faiss_id

                print(f"Memory Synthesizer ({npc_id}): Saved memory to FAISS with ID {current_next_faiss_id}. Index size: {faiss_index.ntotal}. Next ID will be: {new_next_faiss_id}")
            except Exception as e:
                print(f"Memory Synthesizer ({npc_id}): Error saving memory to FAISS: {e}")
        elif faiss_index is None:
            print(f"Memory Synthesizer ({npc_id}): FAISS index not available, skipping save.")
        elif memory_embedding_vector is None:
            print(f"Memory Synthesizer ({npc_id}): Embedding not generated, skipping FAISS save.")

    except Exception as e:
        print(f"Memory Synthesizer ({npc_id}): Error during Groq API call or processing: {e}")
    
    return {"memory_update": memory_update_text, **updated_faiss_components} 