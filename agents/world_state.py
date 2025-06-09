# agents/world_state.py

import random

class WorldState:
    def __init__(self, simulation_time: int = 0):
        # Base time counter (in “ticks”; you can treat each tick as one “turn”)
        self.simulation_time = simulation_time

        # Derive other fields from simulation_time
        self.time_of_day = self._compute_time_of_day()
        self.location = self._compute_location()
        self.weather = self._compute_weather()

    def _compute_time_of_day(self) -> str:
        """
        Simple example: cycle through 4 states every 6 ticks.
        0-5   : Morning
        6-11  : Afternoon
        12-17 : Evening
        18-23 : Night
        (then wrap around)
        """
        hour = self.simulation_time % 24
        if 0 <= hour < 6:
            return "Night"
        elif 6 <= hour < 12:
            return "Morning"
        elif 12 <= hour < 18:
            return "Afternoon"
        else:
            return "Evening"

    def _compute_location(self) -> str:
        """
        Placeholder logic: you could advance location every X ticks, or read from a more complex schedule.
        For now, let’s just pick a static “Town Square” for all turns.
        """
        # In a real setup you might vary this (e.g. wander NPC through multiple locations).
        return "Town Square"

    def _compute_weather(self) -> str:
        """
        Placeholder: randomly choose weather once per day (every 24 ticks).
        For simplicity, we pick at the start of each 24‐tick cycle.
        """
        day = self.simulation_time // 24
        random.seed(day)  # so weather stays consistent for the entire “day”
        return random.choice(["Sunny", "Cloudy", "Rainy", "Windy", "Foggy"])

    def tick(self) -> None:
        """
        Advance simulation_time by 1 tick, and recompute all derived fields.
        """
        self.simulation_time += 1
        self.time_of_day = self._compute_time_of_day()
        self.location = self._compute_location()
        self.weather = self._compute_weather()

    def get_state(self) -> dict:
        """
        Return a dict containing all world‐state variables.
        """
        return {
            "simulation_time": self.simulation_time,
            "time_of_day": self.time_of_day,
            "location": self.location,
            "weather": self.weather,
        }


def world_state_node(input_data: dict) -> dict:
    """
    Node that runs each turn. Expects `input_data` to carry over any previous world state.
    If this is the first turn, we initialize from scratch; otherwise we advance.
    """
    # If there was a previous `simulation_time` in the state, carry it over; else start at 0.
    prev_time = input_data.get("simulation_time", 0)

    # Instantiate our WorldState object from prev_time
    world = WorldState(simulation_time=prev_time)
    # Advance one tick
    world.tick()

    # Print for debugging
    print(f"World State ticked → time={world.simulation_time}, "
          f"time_of_day={world.time_of_day}, location={world.location}, weather={world.weather}")

    # The node should return all derived fields so they merge into the shared state
    return {
        "simulation_time": world.simulation_time,
        "time_of_day": world.time_of_day,
        "location": world.location,
        "weather": world.weather,
    }
