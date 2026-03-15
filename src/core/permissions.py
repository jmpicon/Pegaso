import yaml
import os
from pathlib import Path
from typing import List

class PermissionManager:
    def __init__(self, config_path="config/permissions.yaml"):
        # Detect environment to adjust paths if needed
        self.config_path = config_path
        self.load_config()
        
    def load_config(self):
        if not os.path.exists(self.config_path):
            # Fallback for local testing outside docker
            self.config = {
                'allowlist': {'paths': ['./data/vault'], 'commands': ['ls', 'cat']},
                'capabilities': {'can_write_vault': False}
            }
            return
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
    def is_path_allowed(self, path: str) -> bool:
        try:
            full_path = str(Path(path).resolve())
            for allowed in self.config['allowlist']['paths']:
                allowed_res = str(Path(allowed).resolve())
                if full_path.startswith(allowed_res):
                    return True
            return False
        except Exception:
            return False

    def get_allowed_commands(self) -> List[str]:
        return self.config['allowlist'].get('commands', [])

    def check_command(self, command: str) -> bool:
        if not command: return False
        base_cmd = command.split()[0]
        return base_cmd in self.get_allowed_commands()

# Singleton instance
permissions = PermissionManager()
