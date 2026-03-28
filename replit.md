# NPC LangGraph Simulation

## Overview
A Python-based LLM-driven NPC simulation framework that uses LangGraph state machines, Groq LLM inference, and FAISS vector memory. Exposes a FastAPI HTTP API intended for integration with game engines (Unreal Engine 5).

## Architecture
- **Framework**: FastAPI + Uvicorn (HTTP API server)
- **LLM**: Groq (`llama3-8b-8192`) via `GROQ_API_KEY`
- **Memory**: FAISS vector store + sentence-transformers (`all-MiniLM-L6-v2`)
- **State machine**: LangGraph
- **Persistence**: JSON + FAISS index files in `savegame/`

## Project Structure
- `api.py` — FastAPI server with `/load`, `/tick`, `/save` endpoints
- `main.py` — CLI entry point for a single simulation tick
- `agents/` — LangGraph node implementations (character, memory, quest, world state)
- `workflows/npc_simulation_graph.py` — LangGraph graph definition
- `persistence.py` — Save/load simulation state
- `quests.json` — Quest definitions
- `savegame/` — Persisted state files (state.json + FAISS indices)
- `unreal/` — Unreal Engine 5 C++ client component (not run in Replit)

## Running
- **Workflow**: `uvicorn api:app --host 0.0.0.0 --port 5000`
- **API Docs**: Visit `/docs` for interactive Swagger UI

## API Endpoints
- `POST /load` — Return current simulation state as JSON
- `POST /tick` — Advance one simulation tick (body: `{"event": "...", "params": {...}}`)
- `POST /save` — Force save state to disk

## Environment Variables / Secrets
- `GROQ_API_KEY` — Required for LLM dialogue generation and memory summarization

## NPCs (default)
- `malrik_merchant` — Sharp-eyed merchant with spice_pouch
- `helena_guard` — Steadfast town guard with spear and shield
- `rowan_bard` — Traveling bard with lute and scroll
