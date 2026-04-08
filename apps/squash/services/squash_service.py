"""Squash TM service layer."""
from typing import List, Dict, Any, Optional
from apps.squash.client import SquashClient, SquashClientError


class SquashService:
    """Service for Squash TM operations."""

    def __init__(self, base_url: str, token: str):
        self.client = SquashClient(base_url, token)

    @classmethod
    def from_user(cls, user: dict) -> Optional["SquashService"]:
        """Create a SquashService from user credentials."""
        url = user.get("squash_url")
        token = user.get("squash_token")
        if not url or not token:
            return None
        return cls(url, token)

    def validate_credentials(self) -> bool:
        """Check if credentials are valid."""
        return self.client.validate_token()

    def get_projects_list(self) -> List[Dict[str, Any]]:
        """Get list of projects user has access to."""
        return self.client.get_projects()

    def get_campaign_structure(self, campaign_id: int) -> Dict[str, Any]:
        """Get campaign with its iterations."""
        campaign = self.client.get_campaign(campaign_id)
        iterations = self.client.get_iterations(campaign_id)
        campaign["iterations"] = iterations
        return campaign

    def get_iteration_tests(self, iteration_id: int) -> List[Dict[str, Any]]:
        """Get test plan items for an iteration."""
        return self.client.get_iteration_test_plan(iteration_id)

    def update_test_result(
        self,
        iteration_id: int,
        test_plan_item_id: int,
        status: str,
        comment: str = None
    ) -> Dict[str, Any]:
        """
        Update test execution result in Squash.
        
        Args:
            iteration_id: Iteration ID
            test_plan_item_id: Test plan item ID
            status: Result status (SUCCESS, FAILURE, BLOCKED, etc.)
            comment: Optional comment
        
        Returns:
            Execution data
        """
        return self.client.create_and_update_execution(
            iteration_id, test_plan_item_id, status, comment
        )
