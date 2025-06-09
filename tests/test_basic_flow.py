import unittest
from unittest.mock import patch, MagicMock

from workflows.npc_simulation_graph import build_graph
from agents.player_simulator import player_simulator_node

# Expected responses from mocked LLM calls for consistent testing
MOCKED_LLM_CHARACTER_RESPONSE = "This is a mocked LLM character response for testing."
MOCKED_LLM_MEMORY_SUMMARY = "This is a mocked LLM memory summary for testing."

# Default NPC attributes for testing
DEFAULT_NPC_ATTRIBUTES = {
    "npc_id": "test_npc_001",
    "npc_personality": "a test personality (e.g., perpetually confused)",
    "npc_emotion_state": "curious",
    "npc_inventory_description": "a rubber chicken and a map of an unknown place",
    "passthrough_data": None
}

class TestBasicFlow(unittest.TestCase):

    def test_graph_builds(self):
        try:
            graph = build_graph()
            self.assertIsNotNone(graph, "Graph should not be None after building.")
        except Exception as e:
            self.fail(f"Graph building failed with exception: {e}")

    @patch('agents.memory_synthesizer.client.chat.completions.create') # Patches memory first
    @patch('agents.character_agent.client.chat.completions.create')    # Then character agent
    def test_simulation_flow_with_simulator_input(self, mock_character_groq_create, mock_memory_groq_create):
        # Configure mock for CharacterAgent LLM call
        mock_char_response_obj = MagicMock()
        mock_char_response_obj.choices = [MagicMock()]
        mock_char_response_obj.choices[0].message = MagicMock()
        mock_char_response_obj.choices[0].message.content = MOCKED_LLM_CHARACTER_RESPONSE
        mock_character_groq_create.return_value = mock_char_response_obj

        # Configure mock for MemorySynthesizer LLM call
        mock_mem_summary_obj = MagicMock()
        mock_mem_summary_obj.choices = [MagicMock()]
        mock_mem_summary_obj.choices[0].message = MagicMock()
        mock_mem_summary_obj.choices[0].message.content = MOCKED_LLM_MEMORY_SUMMARY
        mock_memory_groq_create.return_value = mock_mem_summary_obj
        
        graph = build_graph()
        player_sim_data = player_simulator_node()
        initial_input = {"player_input": player_sim_data["player_input"], **DEFAULT_NPC_ATTRIBUTES}

        final_output_container = None 
        final_graph_state_for_memory_check = None # To store the state that should contain memory_update

        for event in graph.stream(initial_input):
            if "__end__" in event:
                final_graph_state_for_memory_check = event["__end__"]
                if isinstance(event["__end__"].get("dialogue_output"), dict):
                    final_output_container = event["__end__"]["dialogue_output"]
                break 
            if "dialogue_manager" in event:
                dm_node_output = event["dialogue_manager"]
                if isinstance(dm_node_output, dict) and \
                   isinstance(dm_node_output.get("dialogue_output"), dict) and \
                   dm_node_output["dialogue_output"].get("final_response"):
                    final_output_container = dm_node_output["dialogue_output"]
                    # The state passed to dialogue_manager when it produces final_response will contain the memory_update
                    final_graph_state_for_memory_check = dm_node_output["dialogue_output"].get("data")

        self.assertIsNotNone(final_output_container, "Could not find a container for final_response.")
        final_response = final_output_container.get("final_response")
        self.assertEqual(MOCKED_LLM_CHARACTER_RESPONSE, final_response, "Final response should be the mocked character LLM response.")
        
        self.assertIsNotNone(final_graph_state_for_memory_check, "Could not find state containing memory_update.")
        memory_update = final_graph_state_for_memory_check.get("memory_update")
        self.assertEqual(MOCKED_LLM_MEMORY_SUMMARY, memory_update, "Memory update should be the mocked LLM summary.")

        mock_character_groq_create.assert_called_once()
        mock_memory_groq_create.assert_called_once()

    @patch('agents.memory_synthesizer.client.chat.completions.create')
    @patch('agents.character_agent.client.chat.completions.create')
    @patch('builtins.input', return_value='Hi there NPC from test')
    def test_simulation_flow_with_user_input(self, mock_input, mock_character_groq_create, mock_memory_groq_create):
        # Configure mock for CharacterAgent LLM call
        mock_char_response_obj = MagicMock()
        mock_char_response_obj.choices = [MagicMock()]
        mock_char_response_obj.choices[0].message = MagicMock()
        mock_char_response_obj.choices[0].message.content = MOCKED_LLM_CHARACTER_RESPONSE
        mock_character_groq_create.return_value = mock_char_response_obj

        # Configure mock for MemorySynthesizer LLM call
        mock_mem_summary_obj = MagicMock()
        mock_mem_summary_obj.choices = [MagicMock()]
        mock_mem_summary_obj.choices[0].message = MagicMock()
        mock_mem_summary_obj.choices[0].message.content = MOCKED_LLM_MEMORY_SUMMARY
        mock_memory_groq_create.return_value = mock_mem_summary_obj

        graph = build_graph()
        initial_input = {"player_input": "Hi there NPC from test", **DEFAULT_NPC_ATTRIBUTES}

        final_output_container = None
        final_graph_state_for_memory_check = None

        for event in graph.stream(initial_input):
            if "__end__" in event:
                final_graph_state_for_memory_check = event["__end__"]
                if isinstance(event["__end__"].get("dialogue_output"), dict):
                    final_output_container = event["__end__"]["dialogue_output"]
                break
            if "dialogue_manager" in event:
                dm_node_output = event["dialogue_manager"]
                if isinstance(dm_node_output, dict) and \
                   isinstance(dm_node_output.get("dialogue_output"), dict) and \
                   dm_node_output["dialogue_output"].get("final_response"):
                    final_output_container = dm_node_output["dialogue_output"]
                    final_graph_state_for_memory_check = dm_node_output["dialogue_output"].get("data")

        self.assertIsNotNone(final_output_container, "Could not find a container for final_response (user input).")
        final_response = final_output_container.get("final_response")
        self.assertEqual(MOCKED_LLM_CHARACTER_RESPONSE, final_response, "Final response for user input should be mocked char response.")

        self.assertIsNotNone(final_graph_state_for_memory_check, "Could not find state containing memory_update (user input).")
        memory_update = final_graph_state_for_memory_check.get("memory_update")
        self.assertEqual(MOCKED_LLM_MEMORY_SUMMARY, memory_update, "Memory update for user input should be mocked summary.")

        mock_character_groq_create.assert_called_once()
        mock_memory_groq_create.assert_called_once()

if __name__ == '__main__':
    unittest.main() 