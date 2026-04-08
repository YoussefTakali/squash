"""Abstract base repository interface."""
from abc import ABC, abstractmethod
from typing import Optional, List


class UserRepositoryInterface(ABC):
    """Abstract interface for user data access."""

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[dict]:
        """Get user by ID."""
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[dict]:
        """Get user by username."""
        pass

    @abstractmethod
    def get_all(self) -> List[dict]:
        """Get all users."""
        pass

    @abstractmethod
    def save(self, user: dict) -> dict:
        """Create or update a user."""
        pass

    @abstractmethod
    def delete(self, user_id: str) -> bool:
        """Delete a user by ID."""
        pass
