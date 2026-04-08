"""Test execution service."""
import subprocess
import threading
from datetime import datetime
from typing import Dict, Any, List, Callable
from dataclasses import dataclass

from apps.projects.services.listener_service import ListenerService
from apps.projects.services.project_service import ProjectService


@dataclass
class ExecutionResult:
    """Result of a test execution."""
    success: bool
    return_code: int
    stdout: str
    stderr: str
    duration: float
    started_at: str
    finished_at: str


class ExecutionService:
    """Service for executing Robot Framework tests."""

    def __init__(self):
        self.listener_service = ListenerService()
        self.project_service = ProjectService()

    def prepare_execution(
        self,
        project_id: str,
        user: dict,
        test_files: List[str] = None
    ) -> Dict[str, Any]:
        """Prepare for test execution by deploying listener and config."""
        project = self.project_service.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        
        squash_url = user.get("squash_url")
        token = user.get("squash_token")
        iteration_id = project.get("squash_iteration_id")
        
        if not squash_url or not token:
            raise ValueError("Squash credentials not configured")
        
        if not iteration_id:
            raise ValueError("Squash iteration ID not configured for this project")
        
        mappings = self.project_service.get_mappings_dict(project_id)
        
        if not mappings:
            raise ValueError("No test mappings configured")
        
        paths = self.listener_service.create_listener_package(
            project_directory=project["directory_path"],
            squash_url=squash_url,
            token=token,
            iteration_id=iteration_id,
            mappings=mappings
        )
        
        command = self.listener_service.get_robot_command(
            project_directory=project["directory_path"],
            test_files=test_files
        )
        
        return {
            "project": project,
            "paths": {k: str(v) for k, v in paths.items()},
            "command": command,
            "mappings_count": len(mappings),
        }

    def execute_tests(
        self,
        project_id: str,
        user: dict,
        test_files: List[str] = None,
        callback: Callable[[str], None] = None
    ) -> ExecutionResult:
        """Execute Robot Framework tests with Squash listener."""
        prep = self.prepare_execution(project_id, user, test_files)
        project = prep["project"]
        command = prep["command"]
        
        started_at = datetime.utcnow()
        
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=project["directory_path"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            stdout_lines = []
            stderr_lines = []
            
            def read_output(pipe, lines, cb):
                for line in iter(pipe.readline, ""):
                    lines.append(line)
                    if cb:
                        cb(line)
                pipe.close()
            
            stdout_thread = threading.Thread(
                target=read_output,
                args=(process.stdout, stdout_lines, callback)
            )
            stderr_thread = threading.Thread(
                target=read_output,
                args=(process.stderr, stderr_lines, None)
            )
            
            stdout_thread.start()
            stderr_thread.start()
            
            return_code = process.wait()
            stdout_thread.join()
            stderr_thread.join()
            
            finished_at = datetime.utcnow()
            
            return ExecutionResult(
                success=return_code == 0,
                return_code=return_code,
                stdout="".join(stdout_lines),
                stderr="".join(stderr_lines),
                duration=(finished_at - started_at).total_seconds(),
                started_at=started_at.isoformat(),
                finished_at=finished_at.isoformat()
            )
            
        except Exception as e:
            finished_at = datetime.utcnow()
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                duration=(finished_at - started_at).total_seconds(),
                started_at=started_at.isoformat(),
                finished_at=finished_at.isoformat()
            )
