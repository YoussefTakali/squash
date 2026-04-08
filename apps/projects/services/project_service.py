"""Project management service."""
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from apps.projects.repositories.json_repository import JsonProjectRepository


class ProjectService:
    """Service for project management operations."""

    def __init__(self, repo: JsonProjectRepository = None):
        self.repo = repo or JsonProjectRepository()

    def create_project(self, user_id: str, name: str, directory_path: str) -> Dict[str, Any]:
        """Create a new project and scan for .robot files."""
        path = Path(directory_path)
        
        if not path.exists():
            raise ValueError(f"Directory does not exist: {directory_path}")
        
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")
        
        # Scan for .robot files
        test_suites = self._scan_robot_files(path)
        
        if not test_suites:
            raise ValueError(f"No .robot files found in: {directory_path}")
        
        project = {
            "user_id": user_id,
            "name": name,
            "directory_path": str(path.resolve()),
            "squash_campaign_id": None,
            "squash_iteration_id": None,
            "test_suites": test_suites,
            "listener_installed": False,
        }
        
        return self.repo.save(project)

    def _scan_robot_files(self, directory: Path) -> List[Dict[str, Any]]:
        """Scan a directory for .robot files and parse test cases."""
        test_suites = []
        
        for robot_file in directory.rglob("*.robot"):
            test_cases = self._parse_robot_file(robot_file)
            if test_cases:
                test_suites.append({
                    "file_path": str(robot_file.relative_to(directory)),
                    "test_cases": test_cases
                })
        
        return test_suites

    def _parse_robot_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse a .robot file and extract test case names."""
        test_cases = []
        in_test_cases_section = False
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip()
                    
                    # Check for section headers
                    if line.startswith("***"):
                        section_name = line.strip("* ").lower()
                        in_test_cases_section = "test case" in section_name or "task" in section_name
                        continue
                    
                    # If in test cases section and line starts with non-whitespace
                    if in_test_cases_section and line and not line[0].isspace():
                        test_name = line.strip()
                        if test_name and not test_name.startswith("#"):
                            test_cases.append({
                                "name": test_name,
                                "squash_test_case_id": None
                            })
        except Exception:
            pass
        
        return test_cases

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get a project by ID."""
        return self.repo.get_by_id(project_id)

    def get_user_projects(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all projects for a user."""
        return self.repo.get_by_user(user_id)

    def rescan_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Rescan a project directory for .robot files."""
        project = self.repo.get_by_id(project_id)
        if not project:
            return None
        
        path = Path(project["directory_path"])
        if not path.exists():
            raise ValueError(f"Directory no longer exists: {project['directory_path']}")
        
        # Preserve existing mappings
        existing_mappings = {}
        for suite in project.get("test_suites", []):
            for tc in suite.get("test_cases", []):
                if tc.get("squash_test_case_id"):
                    existing_mappings[tc["name"]] = tc["squash_test_case_id"]
        
        # Rescan
        test_suites = self._scan_robot_files(path)
        
        # Restore mappings
        for suite in test_suites:
            for tc in suite.get("test_cases", []):
                if tc["name"] in existing_mappings:
                    tc["squash_test_case_id"] = existing_mappings[tc["name"]]
        
        project["test_suites"] = test_suites
        return self.repo.save(project)

    def update_squash_config(self, project_id: str, campaign_id: int = None, iteration_id: int = None) -> Optional[Dict[str, Any]]:
        """Update Squash campaign/iteration IDs for a project."""
        project = self.repo.get_by_id(project_id)
        if not project:
            return None
        
        if campaign_id is not None:
            project["squash_campaign_id"] = campaign_id
        if iteration_id is not None:
            project["squash_iteration_id"] = iteration_id
        
        return self.repo.save(project)

    def update_test_mapping(self, project_id: str, robot_test_name: str, squash_test_case_id: int) -> Optional[Dict[str, Any]]:
        """Update mapping between Robot test and Squash test case."""
        return self.repo.update_mapping(project_id, robot_test_name, squash_test_case_id)

    def update_all_mappings(self, project_id: str, mappings: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Update all test mappings at once."""
        project = self.repo.get_by_id(project_id)
        if not project:
            return None
        
        for suite in project.get("test_suites", []):
            for tc in suite.get("test_cases", []):
                if tc["name"] in mappings:
                    tc["squash_test_case_id"] = mappings[tc["name"]]
        
        return self.repo.save(project)

    def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        return self.repo.delete(project_id)

    def get_all_test_cases(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all test cases from a project with their file paths."""
        project = self.repo.get_by_id(project_id)
        if not project:
            return []
        
        result = []
        for suite in project.get("test_suites", []):
            for tc in suite.get("test_cases", []):
                result.append({
                    "file_path": suite["file_path"],
                    "name": tc["name"],
                    "squash_test_case_id": tc.get("squash_test_case_id")
                })
        
        return result

    def get_mappings_dict(self, project_id: str) -> Dict[str, int]:
        """Get all mappings as a dict for the listener."""
        test_cases = self.get_all_test_cases(project_id)
        return {
            tc["name"]: tc["squash_test_case_id"]
            for tc in test_cases
            if tc.get("squash_test_case_id")
        }
