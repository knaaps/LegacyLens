import os
import json
import hashlib
from pathlib import Path
from typing import Optional

def explanation_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()

class AblationCache:
    def __init__(self, cache_dir: str = ".ablation_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def _get_path(self, func_id: str, arm_config: str, model: str) -> Path:
        safe_func = func_id.replace("/", "_").replace(" ", "_")
        safe_model = model.replace(":", "_").replace("/", "_")
        filename = f"{safe_func}_{arm_config}_{safe_model}.json"
        return self.cache_dir / filename
        
    def get_explanation(self, function_id: str, arm_config: str, model: str) -> Optional[dict]:
        path = self._get_path(function_id, arm_config, model)
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return None
        
    def store_explanation(self, function_id: str, arm_config: str, model: str, explanation: dict):
        path = self._get_path(function_id, arm_config, model)
        with open(path, "w") as f:
            json.dump(explanation, f, indent=2)
