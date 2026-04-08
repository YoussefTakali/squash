"""Authentication service."""
import hashlib
import secrets
from typing import Optional

from apps.accounts.repositories.base import UserRepositoryInterface
from apps.accounts.repositories.json_repository import JsonUserRepository


class AuthService:
    """Service for handling user authentication."""

    def __init__(self, user_repo: UserRepositoryInterface = None):
        self.user_repo = user_repo or JsonUserRepository()

    def _hash_password(self, password: str, salt: str = None) -> tuple:
        """Hash password with salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return f"{salt}${hashed}", salt

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash."""
        try:
            salt, _ = stored_hash.split('$')
            new_hash, _ = self._hash_password(password, salt)
            return secrets.compare_digest(new_hash, stored_hash)
        except ValueError:
            return False

    def register(self, username: str, password: str) -> dict:
        """Register a new user."""
        # Check if username exists
        if self.user_repo.get_by_username(username):
            raise ValueError("Username already exists")

        password_hash, _ = self._hash_password(password)

        user = {
            'username': username,
            'password_hash': password_hash,
            'squash_token': None,
            'squash_url': None,
        }

        return self.user_repo.save(user)

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """Authenticate user credentials."""
        user = self.user_repo.get_by_username(username)
        if not user:
            return None

        if not self._verify_password(password, user.get('password_hash', '')):
            return None

        return user

    def get_user(self, user_id: str) -> Optional[dict]:
        """Get user by ID."""
        return self.user_repo.get_by_id(user_id)

    def update_squash_credentials(self, user_id: str, squash_url: str, squash_token: str) -> dict:
        """Update user's Squash TM credentials."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        user['squash_url'] = squash_url
        user['squash_token'] = squash_token

        return self.user_repo.save(user)

    def update_password(self, user_id: str, current_password: str, new_password: str) -> dict:
        """Update user's password."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if not self._verify_password(current_password, user.get('password_hash', '')):
            raise ValueError("Current password is incorrect")

        password_hash, _ = self._hash_password(new_password)
        user['password_hash'] = password_hash

        return self.user_repo.save(user)
