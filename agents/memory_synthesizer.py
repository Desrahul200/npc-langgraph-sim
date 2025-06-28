import os
from groq import Groq
from sentence_transformers import SentenceTransformer
from utils.print_utils import summarize_for_printing
import numpy as np
import faiss

# Constants for FAISS
EMBEDDING_DIMENSION = 384

# Load embedding model
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    SENTENCE_TRANSFORMER_AVAILABLE = True
except Exception as e:
    print(f"Warning: could not load SentenceTransformer: {e}")
    embedding_model = None
    SENTENCE_TRANSFORMER_AVAILABLE = False

# Load Groq client
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    GROQ_API_KEY_AVAILABLE = True
except Exception as e:
    print(f"Warning: Groq init failed: {e}")
    client = None
    GROQ_API_KEY_AVAILABLE = False

def memory_synthesizer_node(input_data):
    """
    1) Handle direct memory_update from gossip_node.
    2) Otherwise, summarize the last interaction via Groq & embed via FAISS.
    """
    # 1) Direct memory updates (gossip) ────────────────────────────
    #    We still want to handle the target NPC's new raw memory,
    #    but do NOT return immediately—fall through so the LLM
    #    summarization can also index *this* NPC's own turn.
    current_time = input_data.get("simulation_time", 0)
    if input_data.get("memory_update") and input_data.get("memory_owner"):
        owner = input_data["memory_owner"]
        text  = input_data["memory_update"]
        npc   = input_data["npc_states"][owner]

        # a) Append raw text to the target NPC's memory
        npc["memory"].append(text)

        # b) Embed & index into that NPC's FAISS
        if npc["faiss_index"] is not None and SENTENCE_TRANSFORMER_AVAILABLE and embedding_model:
            vec = embedding_model.encode(text, convert_to_numpy=True)
            if vec.ndim == 1: vec = vec.reshape(1, -1)
            emb = vec.astype("float32")
            norms = np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-12)
            emb /= norms

            mid = npc["next_faiss_id"]
            npc["faiss_index"].add_with_ids(emb, np.array([mid], dtype="int64"))
            npc["faiss_id_to_memory_text"][mid] = {
                "text":      text,
                "npc_id":    owner,
                "timestamp": current_time,
            }
            npc["next_faiss_id"] = mid + 1

        # clear so we don't accidentally re‐process it below
        input_data["memory_update"] = None
        input_data["memory_owner"]  = None

    # 2) Fall back to LLM summarization for the speaking NPC ────────
    #    This will create a concise "X remembers that…" sentence
    #    and index it into *their* FAISS.  That's how Malrik gets
    #    his own memory of the last turn.

    # Debug log
    print("Memory Synthesizer received:", summarize_for_printing(input_data, keys_to_redact=["faiss_index"]))

    params       = input_data.get("event_params", {}) or {}
    npc_id       = params.get("npc_id", "unknown_npc")
    player_input = params.get("text", "(no player text)")
    npc_response = input_data.get("response", "(no NPC response)")
    current_time = input_data.get("simulation_time", 0)

    # safety check
    if npc_id not in input_data["npc_states"]:
        return input_data
    npc = input_data["npc_states"][npc_id]

    # fallback summary
    summary = (
        f"{npc_id} remembers that the player said '{player_input}', "
        f"and {npc_id} replied '{npc_response}'."
    )

    # if no Groq, index fallback and return
    if not GROQ_API_KEY_AVAILABLE or client is None:
        print(f"MemorySynthesizer ({npc_id}): Groq unavailable, using fallback.")
        npc["memory"].append(summary)
        if npc["faiss_index"] is not None and SENTENCE_TRANSFORMER_AVAILABLE:
            vec = embedding_model.encode(summary, convert_to_numpy=True)
            if vec.ndim == 1:
                vec = vec.reshape(1, -1)
            emb = vec.astype("float32")
            norms = np.linalg.norm(emb, axis=1, keepdims=True)
            norms[norms == 0] = 1e-12
            emb /= norms

            mid = npc["next_faiss_id"]
            npc["faiss_index"].add_with_ids(emb, np.array([mid], dtype='int64'))
            npc["faiss_id_to_memory_text"][mid] = summary
            npc["next_faiss_id"] = mid + 1

        # consume event
        input_data["last_event"]   = None
        input_data["event_params"] = {}
        return input_data

    # build and send prompts
    system_prompt = (
        f"You are a memory module for NPC '{npc_id}'. "
        "Summarize this interaction into one concise sentence, "
        f"starting with '{npc_id} remembers that...'."
    )
    user_prompt = (
        f"Player said: \"{player_input}\"\n"
        f"{npc_id} responded: \"{npc_response}\"\n\n"
        "Summarize as:"
    )

    try:
        chat = client.chat.completions.create(
            messages=[
                {"role":"system","content":system_prompt},
                {"role":"user",  "content":user_prompt}
            ],
            model="llama3-8b-8192",
            temperature=0.5,
            max_tokens=60
        )
        llm_summary = chat.choices[0].message.content.strip()
        if llm_summary:
            summary = llm_summary
        print(f"MemorySynthesizer ({npc_id}): LLM summary: {summary}")
    except Exception as e:
        print(f"MemorySynthesizer ({npc_id}): LLM error {e}, using fallback.")

    # append to raw memory
    npc["memory"].append(summary)

    # embed + index the summary
    if npc["faiss_index"] is not None and SENTENCE_TRANSFORMER_AVAILABLE:
        try:
            vec = embedding_model.encode(summary, convert_to_numpy=True)
            if vec.ndim == 1:
                vec = vec.reshape(1, -1)
            emb = vec.astype("float32")
            norms = np.linalg.norm(emb, axis=1, keepdims=True)
            norms[norms == 0] = 1e-12
            emb /= norms

            mid = npc["next_faiss_id"]
            npc["faiss_index"].add_with_ids(emb, np.array([mid], dtype='int64'))
            npc["faiss_id_to_memory_text"][mid] = {
                "text":      summary,
                "timestamp": current_time
            }
            npc["faiss_id_to_memory_text"][mid] = {
                    "text":      summary,
                    "npc_id":    npc_id,
                   "timestamp": current_time
                }
            npc["next_faiss_id"] = mid + 1
        except Exception as e:
            print(f"MemorySynthesizer ({npc_id}): Embedding error {e}")

    # finally, consume the event so it doesn't re-fire
    input_data["last_event"]        = None
    input_data["event_params"]      = {}
    input_data["memory_update"]     = None
    input_data["memory_owner"]      = None

    return input_data
