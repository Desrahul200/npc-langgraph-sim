# NPC LangGraph Sim

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](#)
[![Unreal](https://img.shields.io/badge/Unreal-5.6-blueviolet)](#)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](#)

## 📖 Project Overview

**NPC LangGraph Sim** is a prototype of a rich, LLM-driven non-player-character (NPC) simulation framework, featuring:

- **FAISS-backed memory**: NPCs index and retrieve past interactions via vector embeddings  
- **Dynamic quest engine**: quests spawn from gossip or world events, are offered, accepted/declined and then completed  
- **Narrative director**: rule-based world events and story beats inject context into the simulation  
- **Gossip system**: private, NPC-to-NPC rumor spreading  
- **Persistence layer**: full `SimulationState` + FAISS indices snapshot to disk  
- **FastAPI HTTP API**: expose `/load`, `/tick`, `/save` endpoints for real-time integration with Unreal, Unity or any engine  
- **Unreal Engine 5.6 Demo**: C++ component that drives the LLM-powered NPC simulation from inside Unreal Engine

---

## 🔑 Key Features

- **Multi-turn, branching dialogue** with memory recall  
- **Quest lifecycle**: automatic trigger detection, offer, yes/no handling, and completion  
- **World state simulation**: time of day, weather, NPC emotions and inventories  
- **Seamless persistence**: resume play sessions exactly where you left off  
- **Engine-agnostic API**: easy to hook into any front end or game engine  
- **Unreal Integration**: C++ component with Blueprint support for easy game integration

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.9 or newer (for backend simulation)
- **pip** for installing dependencies
- (Optional) **GROQ API key** for high-quality LLM completions
- **Unreal Engine 5.6** (Launcher build is fine) - for Unreal demo
- **Visual Studio 2022 Community** with "Desktop development with C++" workload - for Unreal demo

### Configuration

Create a `.env` file in project root:

```ini
GROQ_API_KEY=your_groq_api_key
```

If you omit `GROQ_API_KEY`, the sim will fallback to simple rule-based summaries.

The save directory defaults to `savegame/`. You can change it in `main.py` or `api.py`.

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd npc-langgraph-sim
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables (optional):
```bash
cp .env.example .env
# Edit .env with your GROQ API key
```

4. For Unreal Engine demo:
```bash
cd unreal/MyProject            # .uproject lives here
# double-click MyProject.uproject
# Unreal will ask to build – click "Yes"
```

---

## 📂 Directory Structure

```
npc-langgraph-sim/
├── agents/                 # LangGraph node implementations
│   ├── character_agent.py
│   ├── memory_synthesizer.py
│   ├── narrative_director.py
│   ├── quest_manager.py
│   ├── quest_offer.py
│   ├── quest_response.py
│   ├── quest_completion.py
│   └── ...
├── workflows/
│   └── npc_simulation_graph.py    # Graph definition & routing
├── persistence.py         # save_state / load_state helpers
├── main.py                # CLI entrypoint
├── api.py                 # FastAPI HTTP server
├── quests.json            # Quest configuration
├── requirements.txt
├── README.md
├── savegame/              # auto-generated state & FAISS indices
└── unreal/                # Unreal Engine 5.6 demo project
    └── MyProject/
        ├── MyProject.uproject
        ├── Source/
        │   └── MyProject/
        │       ├── SimClientComponent.h
        │       └── SimClientComponent.cpp
        ├── Content/
        └── Config/
```

---

## 💻 Usage

### 1. Command-Line Interface

Run a single tick via CLI:

```bash
python main.py --input_type user --text "Hello, how are you?"
```

**Options:**
- `--input_type`:
  - `user` — you type the player line
  - `simulator` — runs built-in simulated player logic
- `--text` — the player's message (when using `user` mode)

Saves state to `savegame/` on every tick. Reloads `savegame/` on start if present.

### 2. HTTP API

Start the server:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

**Endpoints:**

#### POST `/load`
Returns current simulation state

```json
{ "state": { /* SimulationState JSON */ } }
```

#### POST `/tick`
Advance one tick. Request body:

```json
{
  "event": "player_chat",
  "params": {
    "npc_id": "malrik_merchant",
    "text": "Hello!"
  }
}
```

Response:

```json
{ "state": { /* full SimulationState including updated response */ } }
```

#### POST `/save`
Persist state to disk. Returns:

```json
{ "status": "ok" }
```

### 3. Unreal Engine Demo

**Run the demo:**
1. Open `unreal/MyProject/MyProject.uproject`
2. Click "Yes" when Unreal asks to build
3. Press **Play-in-Editor**
4. Press **T** → the sample `SimClientComponent` sends a `/tick` to the simulated backend stub and prints the NPC's reply on screen and in the Output Log

---

## 🎮 Unreal Integration

### Component API (C++)

| Method | Purpose | Blueprint-Callable |
|--------|---------|-------------------|
| `CallLoad()` | fetch initial state | ✅ |
| `CallTick(EventName, ParamsJson)` | advance simulation | ✅ |
| `CallSave()` | snapshot state | ✅ |

| Delegate | Payload |
|----------|---------|
| `OnSimStateUpdated` | `FString JsonText` (full state) |

### Example Level Blueprint

```
T-Key (Pressed)
     │
     └─ Get SimClientComponent
            │
            └─ CallTick
                 • EventName  "player_chat"
                 • ParamsJson "{\"npc_id\":\"malrik_merchant\",\"text\":\"Hello!\"}"
Bind OnSimStateUpdated → "Load Json From String" → "Get String Field 'response'" → Print / display in UI.
```

### Enable Plugins

**Unreal Engine:**
- HTTP Requests & JSON Utilities
- HttpClient & JsonUtilities

### Make HTTP Calls

1. **On player input**: POST `/tick` with `player_chat` event
2. **On startup**: POST `/load`
3. **On shutdown or save**: POST `/save`


### Example Integration Code

**Unreal Blueprint:**
1. Create HTTP Request node
2. Set URL to `http://localhost:8000/tick`
3. Set Content-Type to `application/json`
4. Send JSON payload with event and params
5. Parse response to get NPC reply

---

## 🔧 Architecture

### Core Components

1. **Character Agent**: Handles NPC dialogue and decision-making
2. **Memory Synthesizer**: Indexes conversations in FAISS for retrieval
3. **Quest Manager**: Detects quest triggers and manages quest lifecycle
4. **Narrative Director**: Injects world events and story beats
5. **World State**: Manages time, weather, and environmental factors
6. **Persistence Layer**: Saves/loads complete simulation state

### Quest System

Quests are defined in `quests.json`:

```json
{
  "investigate_theft": {
    "triggers": ["thief", "steal", "theft"],
    "offer_text": "I heard you're interested in justice. Would you help me investigate the theft in the Market Plaza?",
    "accept_text": "Thank you! Meet me at the Market Plaza entrance, and we'll start right away.",
    "decline_text": "I understand. If you change your mind, just let me know.",
    "complete_triggers": ["i found the stolen purse", "here is the stolen item"],
    "complete_text": "Excellent work! You've brought the thief to justice. Here's your reward."
  }
}
```

### Memory System

NPCs use FAISS vector embeddings to:
- Index all conversations and events
- Retrieve relevant memories based on semantic similarity
- Maintain context across multiple interactions
- Fall back to recent raw memories if embeddings fail

---

## 🛠 Development

### Adding New NPCs

1. Add NPC definition to `init_fresh_state()` in `main.py`
2. Define personality and starting inventory
3. NPC will automatically get FAISS memory indexing

### Creating New Quests

1. Add quest definition to `quests.json`
2. Define triggers, offer/accept/decline text, and completion triggers
3. Quest will automatically spawn when triggers are detected

### Extending the API

The FastAPI server can be easily extended with new endpoints:

```python
@app.post("/custom_endpoint")
def custom_endpoint():
    # Your custom logic here
    return {"result": "success"}
```

### Unreal Component Development

The `SimClientComponent` can be extended to:
- Add more Blueprint-callable methods
- Implement custom HTTP request handling
- Add UI integration helpers
- Support different simulation backends

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

## 📞 Support

For questions or issues:
- Open an issue on GitHub
- Check the documentation in the code comments
- Review the example integrations above 