"""JSON file-based test suite repository."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from filelock import FileLock, Timeout as FileLockTimeout

from django.conf import settings
from core.exceptions import RepositoryError


class JsonTestSuiteRepository:
    """Repository for test suites stored in JSON file."""

    def __init__(self, file_path: Path = None):
        self.file_path = file_path or settings.TESTS_JSON_PATH
        self.lock_path = Path(str(self.file_path) + '.lock')
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create the JSON file if it doesn't exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_data({'test_suites': []})

    def _read_data(self) -> dict:
        """Read data from JSON file."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {'test_suites': []}
        except IOError as e:
            raise RepositoryError(f"Failed to read tests data: {e}")

    def _write_data(self, data: dict) -> None:
        """Write data to JSON file with file locking."""
        try:
            lock = FileLock(self.lock_path, timeout=10)
            with lock:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str)
        except FileLockTimeout:
            raise RepositoryError("Could not acquire file lock for writing")
        except IOError as e:
            raise RepositoryError(f"Failed to write tests data: {e}")

    def get_by_id(self, suite_id: str) -> Optional[dict]:
        """Get test suite by ID."""
        data = self._read_data()
        for suite in data.get('test_suites', []):
            if suite['id'] == suite_id:
                return suite
        return None

    def get_by_user(self, user_id: str) -> List[dict]:
        """Get all test suites for a user."""
        data = self._read_data()
        return [s for s in data.get('test_suites', []) if s['user_id'] == user_id]

    def get_all(self) -> List[dict]:
        """Get all test suites."""
        data = self._read_data()
        return data.get('test_suites', [])

    def save(self, suite: dict) -> dict:
        """Create or update a test suite."""
        data = self._read_data()
        suites = data.get('test_suites', [])

        # Check if updating existing suite
        if 'id' in suite and suite['id']:
            for i, existing in enumerate(suites):
                if existing['id'] == suite['id']:
                    suite['updated_at'] = datetime.utcnow().isoformat()
                    suites[i] = suite
                    data['test_suites'] = suites
                    self._write_data(data)
                    return suite

        # Create new suite
        suite['id'] = str(uuid.uuid4())
        suite['created_at'] = datetime.utcnow().isoformat()
        suite.setdefault('test_mappings', [])
        suite.setdefault('detected_tests', [])
        suites.append(suite)
        data['test_suites'] = suites
        self._write_data(data)
        return suite

    def delete(self, suite_id: str) -> bool:
        """Delete a test suite by ID."""
        data = self._read_data()
        suites = data.get('test_suites', [])
        original_count = len(suites)

        suites = [s for s in suites if s['id'] != suite_id]
        data['test_suites'] = suites
        self._write_data(data)

        return len(suites) < original_count

    def update_mappings(self, suite_id: str, mappings: List[dict]) -> Optional[dict]:
        """Update test mappings for a suite."""
        suite = self.get_by_id(suite_id)
        if not suite:
            return None

        suite['test_mappings'] = mappings
        return self.save(suite)

    def update_detected_tests(self, suite_id: str, tests: List[str]) -> Optional[dict]:
        """Update detected tests for a suite."""
        suite = self.get_by_id(suite_id)
        if not suite:
            return None

        suite['detected_tests'] = tests
        return self.save(suite)


class JsonExecutionRepository:
    """Repository for test executions stored in JSON file."""

    def __init__(self, file_path: Path = None):
        self.file_path = file_path or settings.EXECUTIONS_JSON_PATH
        self.lock_path = Path(str(self.file_path) + '.lock')
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create the JSON file if it doesn't exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_data({'executions': []})

    def _read_data(self) -> dict:
        """Read data from JSON file."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {'executions': []}
        except IOError as e:
            raise RepositoryError(f"Failed to read executions data: {e}")

    def _write_data(self, data: dict) -> None:
        """Write data to JSON file with file locking."""
        try:
            lock = FileLock(self.lock_path, timeout=10)
            with lock:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str)
        except FileLockTimeout:
            raise RepositoryError("Could not acquire file lock for writing")
        except IOError as e:
            raise RepositoryError(f"Failed to write executions data: {e}")

    def get_by_id(self, execution_id: str) -> Optional[dict]:
        """Get execution by ID."""
        data = self._read_data()
        for execution in data.get('executions', []):
            if execution['id'] == execution_id:
                return execution
        return None

    def get_by_suite(self, suite_id: str, limit: int = 10) -> List[dict]:
        """Get recent executions for a suite."""
        data = self._read_data()
        executions = [e for e in data.get('executions', []) if e['suite_id'] == suite_id]
        # Sort by date descending
        executions.sort(key=lambda x: x.get('executed_at', ''), reverse=True)
        return executions[:limit]

    def save(self, execution: dict) -> dict:
        """Create or update an execution."""
        data = self._read_data()
        executions = data.get('executions', [])

        # Check if updating existing execution
        if 'id' in execution and execution['id']:
            for i, existing in enumerate(executions):
                if existing['id'] == execution['id']:
                    executions[i] = execution
                    data['executions'] = executions
                    self._write_data(data)
                    return execution

        # Create new execution
        execution['id'] = str(uuid.uuid4())
        execution['executed_at'] = datetime.utcnow().isoformat()
        executions.append(execution)
        data['executions'] = executions
        self._write_data(data)
        return execution
