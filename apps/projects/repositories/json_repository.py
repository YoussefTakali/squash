"""JSON file-based project repository."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from filelock import FileLock, Timeout as FileLockTimeout

from django.conf import settings
from core.exceptions import RepositoryError


class JsonProjectRepository:
    """
    Project repository that stores data in a JSON file.
    Thread-safe using file locking.
    """

    def __init__(self, file_path: Path = None):
        self.file_path = file_path or settings.DATA_DIR / "projects.json"
        self.lock_path = Path(str(self.file_path) + ".lock")
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create the JSON file if it does not exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_data({"projects": []})

    def _read_data(self) -> dict:
        """Read data from JSON file."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"projects": []}
        except IOError as e:
            raise RepositoryError(f"Failed to read projects data: {e}")

    def _write_data(self, data: dict) -> None:
        """Write data to JSON file with file locking."""
        try:
            lock = FileLock(self.lock_path, timeout=10)
            with lock:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
        except FileLockTimeout:
            raise RepositoryError("Could not acquire file lock for writing")
        except IOError as e:
            raise RepositoryError(f"Failed to write projects data: {e}")

    def get_by_id(self, project_id: str) -> Optional[dict]:
        """Get project by ID."""
        data = self._read_data()
        for project in data.get("projects", []):
            if project["id"] == project_id:
                return project
        return None

    def get_by_user(self, user_id: str) -> List[dict]:
        """Get all projects for a user."""
        data = self._read_data()
        return [p for p in data.get("projects", []) if p["user_id"] == user_id]

    def get_all(self) -> List[dict]:
        """Get all projects."""
        data = self._read_data()
        return data.get("projects", [])

    def save(self, project: dict) -> dict:
        """Create or update a project."""
        data = self._read_data()
        projects = data.get("projects", [])

        # Check if updating existing project
        if "id" in project and project["id"]:
            for i, existing in enumerate(projects):
                if existing["id"] == project["id"]:
                    project["updated_at"] = datetime.utcnow().isoformat()
                    projects[i] = project
                    data["projects"] = projects
                    self._write_data(data)
                    return project

        # Create new project
        project["id"] = str(uuid.uuid4())
        project["created_at"] = datetime.utcnow().isoformat()
        projects.append(project)
        data["projects"] = projects
        self._write_data(data)
        return project

    def delete(self, project_id: str) -> bool:
        """Delete a project by ID."""
        data = self._read_data()
        projects = data.get("projects", [])
        original_count = len(projects)

        projects = [p for p in projects if p["id"] != project_id]
        data["projects"] = projects
        self._write_data(data)

        return len(projects) < original_count

    def update_test_suites(self, project_id: str, test_suites: List[dict]) -> Optional[dict]:
        """Update test suites for a project."""
        project = self.get_by_id(project_id)
        if not project:
            return None
        
        project["test_suites"] = test_suites
        return self.save(project)

    def update_mapping(self, project_id: str, robot_test_name: str, squash_test_case_id: int) -> Optional[dict]:
        """Update a single test mapping."""
        project = self.get_by_id(project_id)
        if not project:
            return None
        
        for suite in project.get("test_suites", []):
            for test_case in suite.get("test_cases", []):
                if test_case["name"] == robot_test_name:
                    test_case["squash_test_case_id"] = squash_test_case_id
                    return self.save(project)
        
        return None
