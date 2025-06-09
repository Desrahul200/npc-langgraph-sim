import copy

def summarize_for_printing(data_to_summarize, keys_to_redact=None):
    """
    Recursively creates a summarized version of complex data structures
    for printing, redacting specified keys, long embeddings, and summarizing shared_memory.
    Makes a deepcopy of the data before summarizing to avoid side effects.
    """
    if keys_to_redact is None:
        keys_to_redact = []
    
    data = copy.deepcopy(data_to_summarize)

    if not isinstance(data, dict):
        # For non-dict types, summarize if it looks like a long list of numbers
        if isinstance(data, list) and len(data) > 5 and all(isinstance(i, (float, int)) for i in data):
            return f"<list_of_numbers (length: {len(data)})>"
        return data # Return other non-dict types as is

    summary = {}
    for k, v_original in data.items():
        v = v_original

        if k in keys_to_redact:
            summary[k] = f"<redacted_key: {k}>"
            continue # Skip other processing for this key

        if k == "shared_memory":
            if isinstance(v, dict):
                summary["shared_memory_summary"] = {
                    npc_id: f"{len(mems) if isinstance(mems, list) else 'non_list_data'} entries"
                    for npc_id, mems in v.items()
                }
            else:
                summary["shared_memory"] = f"<present (type: {type(v).__name__})>"
        elif k == "embedding" and isinstance(v, list) and len(v) > 3:
            summary[k] = f"<embedding_vector (length: {len(v)})>"
        elif k == "faiss_index" and v is not None: # Specific handling for faiss_index if not in keys_to_redact
             summary[k] = f"<faiss_index (ntotal: {v.ntotal if hasattr(v, 'ntotal') else 'N/A'})>"
        elif isinstance(v, dict):
            summary[k] = summarize_for_printing(v, keys_to_redact=keys_to_redact)  # Pass keys_to_redact recursively
        elif isinstance(v, list):
            # Summarize lists if they contain dicts that need further summarization
            if any(isinstance(item, dict) for item in v):
                summary[k] = [summarize_for_printing(item, keys_to_redact=keys_to_redact) for item in v] # Pass keys_to_redact
            # Or if they look like embeddings themselves (list of floats/ints)
            elif len(v) > 3 and all(isinstance(i, (float, int)) for i in v):
                summary[k] = f"<list_of_numbers (length: {len(v)})>"
            else:
                summary[k] = v # Keep other lists (e.g., short lists, lists of strings) as is
        else:
            summary[k] = v
    return summary 