import os
import json
import numpy as np
import faiss
from groq import Groq
from sentence_transformers import SentenceTransformer
from typing import Any, Dict

# Initialize Groq client
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    GROQ_OK = True
except Exception:
    client = None
    GROQ_OK = False

# Initialize embedding model for FAISS retrieval
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    EMB_OK = True
except Exception:
    embedding_model = None
    EMB_OK = False

def character_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    print(f"Character Agent received: {{npc_id={state['event_params'].get('npc_id')}, text=\"{state['event_params'].get('text')}\"}}")
    # 1) Extract NPC and player input
    params      = state.get("event_params", {}) or {}
    npc_id      = params.get("npc_id", "unknown_npc")
    player_text = params.get("text", "").strip()

    # Fallback if missing
    if npc_id not in state["npc_states"] or not player_text:
        state["response"]    = "…"
        state["tool_action"] = None
        return state

    npc = state["npc_states"][npc_id]
    personality  = npc.get("personality", "an NPC")
    emotion      = npc.get("emotion_state", "neutral")
    inventory    = npc.get("inventory", [])
    inv_desc     = ", ".join(inventory) if inventory else "nothing"
    other_npc_entries = []
    for other_id, other_sub in state["npc_states"].items():
        if other_id == npc_id:
            continue
        # e.g. "helena_guard (steadfast town guard)"
        other_npc_entries.append(f"{other_id} ({other_sub.get('personality','')})")
    other_npcs_str = ", ".join(other_npc_entries) if other_npc_entries else "none"

    # 2) FAISS-based memory recall
    raw = npc["memory"]
    if raw:
        # show last 3 memories if nothing better
        fallback = "\n".join(f" • {m}" for m in raw[-3:])
    else:
        fallback = "I have no specific memories to draw on."

    relevant_memories_str = fallback

    faiss_index = npc.get("faiss_index")
    id2txt      = npc.get("faiss_id_to_memory_text", {})
    now         = state.get("simulation_time", 0)

    if EMB_OK and embedding_model and faiss_index is not None and faiss_index.ntotal > 0:
        # encode & normalize
        vec = embedding_model.encode(player_text, convert_to_numpy=True)
        if vec.ndim == 1: vec = vec.reshape(1, -1)
        vec = vec.astype("float32")
        norms = np.linalg.norm(vec, axis=1, keepdims=True).clip(min=1e-12)
        vec /= norms

        # always retrieve top 5, no score cutoff
        D, I = faiss_index.search(vec, k=5)
        candidates = []
        decay = 0.1
        for score, idx in zip(D[0], I[0]):
            if idx < 0: continue
            entry = id2txt.get(int(idx))
            if not entry or entry.get("npc_id") != npc_id: continue
            age = now - entry.get("timestamp", 0)
            weight = score * max(0.0, 1 - decay * age)
            candidates.append((weight, entry["text"]))
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_texts = [txt for w, txt in candidates[:3]]
        if top_texts:
            relevant_memories_str = "Past memories:\n" + "\n".join(f" • {t}" for t in top_texts)
    
    # 3) Build LLM prompt
    system_prompt = (
        f"You are '{npc_id}', {personality}. You feel '{emotion}'.\n"
        f"Inventory: {inv_desc}.\n"
        f"{relevant_memories_str}\n\n"
        f"Other NPCs you could share gossip with: {other_npcs_str}.\n\n"
        "When you reply, return ONLY valid JSON with these keys:\n"
        "{\n"
        '  "response": string,\n'
        '  "emotion_state": one of [neutral,happy,sad,angry,curious],\n'
        '  "tool_action": { "type": string, "params": {...} } or null\n'
        "}\n\n"
        "# GOSSIP INSTRUCTIONS\n"
        "If you want to share private gossip with another NPC in the world, "
        "set tool_action to:\n"
        '  { "type": "gossip", "params": { '
        '"target_npc": "<that_npc_id>", "message": "<your private message>" } }\n'
        "Otherwise set tool_action to null.\n"
    )
    user_prompt = f"Player says: \"{player_text}\""

    # 4) Call Groq and parse
    response_text = ""
    new_emotion   = emotion
    tool_action   = None

    if GROQ_OK:
        try:
            comp = client.chat.completions.create(
                messages=[
                    {"role":"system","content":system_prompt},
                    {"role":"user",  "content":user_prompt}
                ],
                model="llama3-8b-8192",
                temperature=0.7,
                max_tokens=150,
            )
            raw = comp.choices[0].message.content.strip()
            data = json.loads(raw)
            response_text = data.get("response", "")
            emo = data.get("emotion_state", emotion)
            if emo in {"neutral","happy","sad","angry","curious"}:
                new_emotion = emo
            tool_action = data.get("tool_action")
        except Exception:
            response_text = "…"
    else:
        # simple fallback
        response_text = "I'm not thinking clearly right now."

    # 5) Write back into state
    state["response"]                         = response_text
    state["npc_states"][npc_id]["emotion_state"] = new_emotion
    state["tool_action"]                       = tool_action
    print(f"Character Agent ({npc_id}): recalled memories:\n{relevant_memories_str}")
    return state
