# agents/narrative_director.py

from narrative_rules import NARRATIVE_RULES
from utils.print_utils import summarize_for_printing

def narrative_director_node(input_data):
    """
    Looks at world-state + existing story fields, decides whether to inject a new story beat or quest.
    Returns updated 'narrative_guidance', and writes back into 'active_quests', 'current_story_beat',
    'narrative_cooldown', and 'quest_history'.
    """
    # 1) Unpack relevant fields
    state = input_data  # shorthand
    sim_time = state.get("simulation_time", 0)
    tod = state.get("time_of_day", "")
    location = state.get("location", "")
    weather = state.get("weather", "")
    
    active_quests = state.get("active_quests", [])
    quest_history = state.get("quest_history", [])
    cooldown = state.get("narrative_cooldown", 0)
    
    # Default outputs
    new_guidance = ""
    new_beat = state.get("current_story_beat")  # carry over if nothing changes
    new_active_quests = list(active_quests)    # copy by value
    new_quest_history = list(quest_history)
    new_cooldown = cooldown
    
    print(f"NarrativeDirector received (time={sim_time}, tod={tod}, loc={location}, weather={weather}, cooldown={cooldown})")
    
    # 2) If cooldown > 0, just count down and do nothing else
    if new_cooldown > 0:
        new_cooldown -= 1
        return {
            "narrative_guidance": "",
            "current_story_beat": new_beat,
            "active_quests": new_active_quests,
            "narrative_cooldown": new_cooldown,
            "quest_history": new_quest_history,
        }
    
    # 3) Otherwise, find the first rule whose condition matches
    matched = None
    for rule in NARRATIVE_RULES:
        try:
            if rule["when"](state):
                matched = rule
                break
        except Exception:
            # If a rule’s lambda crashes for missing keys, skip it
            continue
    
    if matched is None:
        # Shouldn't happen if you have a fallback rule (always_true)
        new_guidance = ""
        new_beat = None
    else:
        new_beat = matched["beat"]
        new_guidance = matched["guidance"]
        quest_id = matched.get("quest_id")
        
        # 4) If this rule introduces a quest, and it’s not already active
        if quest_id is not None and quest_id not in new_active_quests:
            new_active_quests.append(quest_id)
            new_quest_history.append(quest_id)
        
        # 5) Reset a cooldown so we don’t fire again for N turns
        new_cooldown = 3  # e.g. wait 3 ticks before injecting another beat
    
    # 6) Return everything we updated
    return {
        "narrative_guidance": new_guidance,
        "current_story_beat": new_beat,
        "active_quests": new_active_quests,
        "narrative_cooldown": new_cooldown,
        "quest_history": new_quest_history,
        # We do not override passthrough_data here; just pass it along
        "passthrough_data": state.get("passthrough_data"),
    }
