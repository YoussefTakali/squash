"""JSON file-based user repository."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from filelock import FileLock, Timeout as FileLockTimeout

from django.conf import settings
from core.exceptions import RepositoryError
from .base import UserRepositoryInterface


class JsonUserRepository(UserRepositoryInterface):
    """
    User repository that stores data in a JSON file.
    Thread-safe using file locking.
    """

    def __init__(self, file_path: Path = None):
        self.file_path = file_path or settings.USERS_JSON_PATH
        self.lock_path = Path(str(self.file_path) + '.lock')
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create the JSON file if it doesn't exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_data({'users': []})

    def _read_data(self) -> dict:
        """Read data from JSON file."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {'users': []}
        except IOError as e:
            raise RepositoryError(f"Failed to read users data: {e}")

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
            raise RepositoryError(f"Failed to write users data: {e}")

    def get_by_id(self, user_id: str) -> Optional[dict]:
        """Get user by ID."""
        data = self._read_data()
        for user in data.get('users', []):
            if user['id'] == user_id:
                return user
        return None

    def get_by_username(self, username: str) -> Optional[dict]:
        """Get user by username."""
        data = self._read_data()
        for user in data.get('users', []):
            if user['username'].lower() == username.lower():
                return user
        return None

    def get_all(self) -> List[dict]:
        """Get all users."""
        data = self._read_data()
        return data.get('users', [])

    def save(self, user: dict) -> dict:
        """Create or update a user."""
        data = self._read_data()
        users = data.get('users', [])

        # Check if updating existing user
        if 'id' in user and user['id']:
            for i, existing in enumerate(users):
                if existing['id'] == user['id']:
                    user['updated_at'] = datetime.utcnow().isoformat()
                    users[i] = user
                    data['users'] = users
                    self._write_data(data)
                    return user

        # Create new user
        user['id'] = str(uuid.uuid4())
        user['created_at'] = datetime.utcnow().isoformat()
        users.append(user)
        data['users'] = users
        self._write_data(data)
        return user

    def delete(self, user_id: str) -> bool:
        """Delete a user by ID."""
        data = self._read_data()
        users = data.get('users', [])
        original_count = len(users)

        users = [u for u in users if u['id'] != user_id]
        data['users'] = users
        self._write_data(data)

        return len(users) < original_count
