import json
from typing import List, Dict, Any, Callable

class ConfigAgent:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.call_vlm = call_vlm or self._default_vlm_call

    def load_config(self, file_path: str) -> List[Dict[str, Any]]:
        """Load configuration file (supports JSON and YAML)"""
        try:
            with open(file_path, 'r') as f:
                if file_path.endswith('.json'):
                    return json.load(f)
                else:
                    raise ValueError("Unsupported file format")
        except Exception as e:
            raise Exception(f"Failed to load config file: {e}")
    
        
    # Usage example:
    # agent = ConfigAgent("config.json", call_vlm_function)
    def compare_items(self, file_path: str, data: List[Dict]) -> bool:
        """Compare items in config file and call VLM if any key mismatches"""
        # Load the config data from file
        config_data = self.load_config(file_path)
        config_data = config_data.get("payload", [])
        # Quick length check
        if len(data) != len(config_data):
            return False

        def normalize(d):
            norm = {}
            for k, v in d.items():
                key = k.lower()
                # Normalize value — handle strings separately
                if isinstance(v, str):
                    value = v.strip().lower()
                else:
                    value = v
                norm[key] = value
            return norm

        normalized1 = [normalize(d) for d in data]
        normalized2 = [normalize(d) for d in config_data]

        # Convert dicts to sorted tuples for comparison
        def dict_to_sorted_tuple(d):
            return tuple(sorted(d.items()))

        set1 = {dict_to_sorted_tuple(d) for d in normalized1}
        set2 = {dict_to_sorted_tuple(d) for d in normalized2}

        return set1 == set2

# Usage example:
# agent = ConfigAgent("config.json")
# agent.compare_items("config.json", data_list)