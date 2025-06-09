# narrative_rules.py

def is_night_and_town_square(state):
    return state["time_of_day"] == "Night" and "Town Square" in state["location"]

def is_festival_day(state):
    # imagine you have a field state["current_event"] == "harvest_festival"
    return state.get("current_event") == "harvest_festival"

def always_true(state):
    return True

NARRATIVE_RULES = [
    {
        "when": is_night_and_town_square,
        "beat": "curfew_warning",
        "guidance": "The town guard is about to lock the gates. NPCs are uneasy. Mention the nighttime curfew.",
        "quest_id": "warn_venue_before_curfew"
    },
    {
        "when": is_festival_day,
        "beat": "festival_celebration",
        "guidance": "The Harvest Festival is in full swing. NPCs are celebrating around the bonfire—ask them for rumors.",
        "quest_id": "gather_festival_supplies"
    },
    {
        "when": always_true,
        "beat": "nothing_special",
        "guidance": "",  # no guidance this turn
        "quest_id": None
    },
]
