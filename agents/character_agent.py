# agents/character_agent.py

import os
from groq import Groq
from sentence_transformers import SentenceTransformer
import numpy as np
from utils.print_utils import summarize_for_printing
import faiss  # Ensure faiss is imported
import json
# Constants
EMBEDDING_DIMENSION = 384  # Should match MemorySynthesizer and main.py

# Initialize SentenceTransformer model
try:
    embedding_model_char = SentenceTransformer('all-MiniLM-L6-v2')
    SENTENCE_TRANSFORMER_AVAILABLE_CHAR = True
    print("SentenceTransformer model loaded successfully for CharacterAgent.")
except Exception as e:
    print(f"Warning: Could not load SentenceTransformer model for CharacterAgent: {e}. Semantic retrieval will not be effective.")
    embedding_model_char = None
    SENTENCE_TRANSFORMER_AVAILABLE_CHAR = False

# Initialize Groq Client
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    GROQ_API_KEY_AVAILABLE = True
except Exception as e:
    print(f"Warning: Groq API key not found or client could not be initialized for CharacterAgent: {e}")
    client = None
    GROQ_API_KEY_AVAILABLE = False

def character_agent_node(input_data):
    print(f"Character Agent received: {summarize_for_printing(input_data, keys_to_redact=['faiss_index'])}")

    npc_id = input_data.get("npc_id", "unknown_npc")
    personality = input_data.get("npc_personality", "a generic NPC")
    emotion_state = input_data.get("npc_emotion_state", "neutral")
    inventory_description = input_data.get("npc_inventory_description", "nothing of note")

    player_input = input_data.get("player_input", "").strip()
    response_text = "I... don't know what to say. (Error in LLM call or no input)"
    updated_emotion_state = emotion_state

    # --- Get FAISS components and current time from input_data ---
    faiss_index = input_data.get("faiss_index")
    faiss_id_to_memory_text = input_data.get("faiss_id_to_memory_text", {})
    current_time = input_data.get("simulation_time", 0)

    if not GROQ_API_KEY_AVAILABLE or not client:
        print(f"Character Agent ({npc_id}): Groq API key/client not available. Returning stubbed response.")
        player_input_lower = player_input.lower()
        if "hello" in player_input_lower or "hi" in player_input_lower:
            response_text = "Hmph. What is it? (Groq not available)"
        else:
            response_text = "I can't seem to think right now. (Groq not available)"
        return {"response": response_text, "npc_emotion_state": updated_emotion_state}

    if not player_input:
        response_text = "You said nothing. What do you want?"
        if personality == "a slightly grumpy but knowledgeable old librarian":
            updated_emotion_state = "annoyed"
        return {"response": response_text, "npc_emotion_state": updated_emotion_state}
    
    # We'll let the LLM pick the new emotion instead of hard-coding it here:
    updated_emotion_state = emotion_state


    # --- FAISS Semantic Memory Retrieval with Time-Weighted Decay ---
    relevant_memories_str = "This is the first time we are meeting, or no specific memories were recalled."
    recalled_memories_count = 0

    # How many raw matches to fetch from FAISS before re-ranking
    num_memories_to_recall = 5
    # Inner‐product threshold (for IndexFlatIP). Only consider anything above this raw score
    similarity_threshold = 0.1

    if (
        player_input
        and SENTENCE_TRANSFORMER_AVAILABLE_CHAR
        and embedding_model_char
        and faiss_index
        and faiss_index.ntotal > 0
    ):
        try:
            # 1) Encode player input
            raw_player_embedding = embedding_model_char.encode(player_input)
            if raw_player_embedding.ndim == 1:
                player_input_embedding_np = np.expand_dims(raw_player_embedding, axis=0)
            else:
                player_input_embedding_np = raw_player_embedding
            player_input_embedding_np = player_input_embedding_np.astype('float32')
            # Normalize to unit length (so inner-product = cosine similarity)
            norms_q = np.linalg.norm(player_input_embedding_np, axis=1, keepdims=True)
            norms_q[norms_q == 0] = 1e-12
            player_input_embedding_np = player_input_embedding_np / norms_q

            print(f"Character Agent ({npc_id}): Searching FAISS index (size: {faiss_index.ntotal}) with input embedding (shape: {player_input_embedding_np.shape})...")

            # 2) Perform raw FAISS search (un‐weighted)
            D, I = faiss_index.search(player_input_embedding_np, k=num_memories_to_recall)
            raw_ids = I[0]
            raw_scores = D[0]

            print(f"Character Agent ({npc_id}): FAISS search results - IDs: {raw_ids}, Scores: {raw_scores}")

            # 3) Build a list of (weighted_score, id, text)
            candidates = []
            decay_rate = 0.1  # Adjust this to control how quickly older memories decay

            for idx, score in zip(raw_ids, raw_scores):
                if idx == -1 or score < similarity_threshold:
                    continue

                # Look up the memory entry
                mem_entry = faiss_id_to_memory_text.get(int(idx))
                if not mem_entry:
                    continue

                # Only recall memories belonging to this NPC
                if mem_entry.get("npc_id") != npc_id:
                    print(f"Character Agent ({npc_id}): Memory ID {idx} belongs to another NPC ({mem_entry.get('npc_id')}). Skipping.")
                    continue

                # Compute age = current_time − timestamp
                ts = mem_entry.get("timestamp", 0)
                age = current_time - ts
                # Linear decay factor (clamped to ≥ 0)
                decay_factor = max(0.0, 1.0 - decay_rate * age)
                weighted_score = score * decay_factor

                print(
                    f"Character Agent ({npc_id}): "
                    f"Memory ID {idx}, raw_score={score:.4f}, timestamp={ts}, age={age}, "
                    f"decay_factor={decay_factor:.3f}, weighted_score={weighted_score:.4f}"
                )

                candidates.append((weighted_score, idx, mem_entry["text"]))

            # 4) Sort candidates by weighted_score descending
            candidates.sort(key=lambda x: x[0], reverse=True)

            # 5) Pick top‐3 after weighting
            top_n = 3
            top_relevant_memories_text = [text for (w, _, text) in candidates[:top_n] if w > 0]
            recalled_memories_count = len(top_relevant_memories_text)

            if top_relevant_memories_text:
                relevant_memories_str = "Relevant recent memories based on your statement:"
                for i, mem_t in enumerate(top_relevant_memories_text):
                    relevant_memories_str += f"\n  Memory {i+1}: {mem_t}"
            else:
                relevant_memories_str = (
                    "I have some memories, but none seem directly relevant to your statement."
                    if faiss_index.ntotal > 0
                    else "I don't seem to have any specific memories stored yet."
                )

        except Exception as e:
            print(f"Character Agent ({npc_id}): Error during FAISS semantic memory retrieval: {e}")
            relevant_memories_str = "I tried to recall our past, but my memory is a bit hazy right now (FAISS error)."
    elif not (SENTENCE_TRANSFORMER_AVAILABLE_CHAR and embedding_model_char):
        relevant_memories_str = "My ability to recall specific memories is limited right now (embedding model issue)."
    else:  # no index or empty
        relevant_memories_str = "I don't seem to have any specific memories stored yet."

    print(f"Character Agent ({npc_id}): Recalled {recalled_memories_count} memories using FAISS.")


    system_prompt = (
        f"You are the NPC '{npc_id}', with personality: {personality}. "
        f"You currently feel: {updated_emotion_state}. "
        f"Your inventory: {inventory_description}.\n"
        f"{relevant_memories_str}\n\n"
        "When the player speaks, return ONLY valid JSON with three keys:\n"
        "{\n"
        '  "response": "<your spoken reply in character>",\n'
        '  "emotion_state": "<one of: angry, annoyed, neutral, happy, sad, excited, confused, curious>"\n'
        '  "tool_action": { "type": "<action_name>", "params": { … } }  // or null if none\n'
        "}\n\n"
        "Answer only with that JSON—do NOT include any extra text.\n"
    )
    user_prompt = f"The player says: \"{player_input}\""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            model="llama3-70b-8192",
            temperature=0.75, max_tokens=200, top_p=0.9,
        )
        llm_output = chat_completion.choices[0].message.content.strip()

        # Attempt to parse JSON. If JSON parsing fails, fall back gracefully.
        try:
            parsed = json.loads(llm_output)
            response_text = parsed.get("response", "").strip()
            new_emotion = parsed.get("emotion_state", "").strip().lower()
            raw_action = parsed.get("tool_action", None)
            tool_action = raw_action if isinstance(raw_action, dict) else None
            # Only accept it if it’s one of our allowed labels:
            if new_emotion in {"angry","annoyed","neutral","happy","sad","excited","confused","curious"}:
                updated_emotion_state = new_emotion
            else:
                # If it’s invalid or missing, keep the old state
                updated_emotion_state = emotion_state
        except Exception:
            # If parsing fails, just treat the entire LLM output as the response,
            # and leave emotion unchanged:
            response_text = llm_output
            updated_emotion_state = emotion_state
            tool_action = None
        print(f"Character Agent ({npc_id}): Received JSON from Groq: {llm_output}")
    except Exception as e:
        print(f"Character Agent ({npc_id}): Error during Groq API call: {e}")
        response_text = f"I seem to be having trouble forming words right now. (Error: {e})"

    return {"response": response_text, "npc_emotion_state": updated_emotion_state, "tool_action": tool_action}
