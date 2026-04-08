"""Listener management service."""
import json
import shutil
from pathlib import Path
from typing import Dict, Any

from django.conf import settings


class ListenerService:
    """Service for managing the Squash listener deployment."""

    LISTENER_FILENAME = "squash_listener.py"
    CONFIG_FILENAME = "squash_config.json"

    def __init__(self):
        self.listener_source = settings.BASE_DIR / "listener" / self.LISTENER_FILENAME

    def generate_config(
        self,
        squash_url: str,
        token: str,
        iteration_id: int,
        mappings: Dict[str, int],
        output_path: Path
    ) -> Path:
        """Generate a listener configuration file."""
        config = {
            "squash_url": squash_url,
            "token": token,
            "iteration_id": iteration_id,
            "mappings": mappings
        }
        
        config_path = Path(output_path) / self.CONFIG_FILENAME
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        
        return config_path

    def deploy_listener(self, target_directory: str) -> Dict[str, Path]:
        """Deploy the listener script to a project directory."""
        target_path = Path(target_directory)
        
        if not target_path.exists():
            raise ValueError(f"Directory does not exist: {target_directory}")
        
        listener_dest = target_path / self.LISTENER_FILENAME
        shutil.copy2(self.listener_source, listener_dest)
        
        return {"listener": listener_dest}

    def create_listener_package(
        self,
        project_directory: str,
        squash_url: str,
        token: str,
        iteration_id: int,
        mappings: Dict[str, int]
    ) -> Dict[str, Path]:
        """Deploy listener and generate config for a project."""
        paths = self.deploy_listener(project_directory)
        
        config_path = self.generate_config(
            squash_url=squash_url,
            token=token,
            iteration_id=iteration_id,
            mappings=mappings,
            output_path=project_directory
        )
        
        paths["config"] = config_path
        return paths

    def get_robot_command(
        self,
        project_directory: str,
        test_files: list = None
    ) -> str:
        """Generate the robot command with listener."""
        listener_path = Path(project_directory) / self.LISTENER_FILENAME
        config_path = Path(project_directory) / self.CONFIG_FILENAME
        
        cmd_parts = [
            "robot",
            f"--listener {listener_path}:{config_path}",
            "--outputdir results",
        ]
        
        if test_files:
            cmd_parts.extend(test_files)
        else:
            cmd_parts.append(".")
        
        return " ".join(cmd_parts)
