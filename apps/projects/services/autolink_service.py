"""Auto-linking service for matching Robot tests to Squash test cases."""
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple

from apps.squash.client import SquashClient, SquashClientError


class AutoLinkService:
    """
    Service for automatically linking Robot Framework tests to Squash TM test cases.

    Uses offline string matching algorithms (no AI, no external services).
    All matching is done locally using Python's difflib.
    """

    # Minimum similarity score to consider a match (0.0 to 1.0)
    DEFAULT_THRESHOLD = 0.6

    def __init__(self, squash_url: str, squash_token: str):
        self.client = SquashClient(squash_url, squash_token)

    @classmethod
    def from_user(cls, user: dict) -> Optional["AutoLinkService"]:
        """Create service from user credentials."""
        url = user.get("squash_url")
        token = user.get("squash_token")
        if not url or not token:
            return None
        return cls(url, token)

    def _normalize_name(self, name: str) -> str:
        """
        Normalize a test name for comparison.

        - Convert to lowercase
        - Replace underscores and hyphens with spaces
        - Remove special characters
        - Collapse multiple spaces
        """
        name = name.lower()
        name = re.sub(r'[_\-]', ' ', name)
        name = re.sub(r'[^a-z0-9\s]', '', name)
        name = re.sub(r'\s+', ' ', name)
        return name.strip()

    def _tokenize(self, name: str) -> List[str]:
        """Split a name into tokens/words."""
        return self._normalize_name(name).split()

    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity score between two names.

        Uses multiple strategies and returns the best score:
        1. Direct sequence matching on normalized names
        2. Token overlap (Jaccard similarity)
        3. Token sequence matching
        """
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)

        # Strategy 1: Direct sequence matching
        direct_score = SequenceMatcher(None, norm1, norm2).ratio()

        # Strategy 2: Token-based Jaccard similarity
        tokens1 = set(self._tokenize(name1))
        tokens2 = set(self._tokenize(name2))

        if tokens1 and tokens2:
            intersection = len(tokens1 & tokens2)
            union = len(tokens1 | tokens2)
            jaccard_score = intersection / union if union > 0 else 0
        else:
            jaccard_score = 0

        # Strategy 3: Token sequence matching (ordered)
        tokens1_list = self._tokenize(name1)
        tokens2_list = self._tokenize(name2)
        token_seq_score = SequenceMatcher(None, tokens1_list, tokens2_list).ratio()

        # Return the best score
        return max(direct_score, jaccard_score, token_seq_score)

    def fetch_squash_test_cases(self, project_id: int = None) -> List[Dict[str, Any]]:
        """
        Fetch all test cases from Squash TM.

        Args:
            project_id: Optional Squash project ID to filter by

        Returns:
            List of test cases with id and name
        """
        try:
            test_cases = self.client.get_test_cases(project_id)
            return [
                {
                    "id": tc.get("id"),
                    "name": tc.get("name", ""),
                    "reference": tc.get("reference", ""),
                    "path": tc.get("path", "")
                }
                for tc in test_cases
            ]
        except SquashClientError:
            return []

    def fetch_squash_campaigns(self, project_id: int = None) -> List[Dict[str, Any]]:
        """Fetch all campaigns from Squash TM."""
        try:
            campaigns = self.client.get_campaigns(project_id)
            return [
                {
                    "id": c.get("id"),
                    "name": c.get("name", ""),
                    "reference": c.get("reference", "")
                }
                for c in campaigns
            ]
        except SquashClientError:
            return []

    def fetch_all_campaign_folders(self) -> List[Dict[str, Any]]:
        """
        Fetch all campaign folders from Squash TM using pagination.
        
        Uses the campaign-folders endpoint with automatic pagination
        to retrieve all folders regardless of total count.
        
        Returns:
            List of campaign folders with id, name, and reference
        """
        try:
            folders = self.client.get_all_campaign_folders()
            return [
                {
                    "id": f.get("id"),
                    "name": f.get("name", ""),
                    "reference": f.get("reference", "")
                }
                for f in folders
            ]
        except SquashClientError:
            return []

    def find_campaign_folder_by_name(self, campaign_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a campaign folder by exact name match.
        
        Fetches all campaign folders using pagination and searches
        for an exact name match.
        
        Args:
            campaign_name: Name of the campaign folder to find
            
        Returns:
            Campaign folder dict with id, name, reference or None
        """
        all_folders = self.fetch_all_campaign_folders()
        
        for folder in all_folders:
            if folder.get("name") == campaign_name:
                return folder
        
        return None

    def fetch_squash_projects(self) -> List[Dict[str, Any]]:
        """Fetch all projects from Squash TM."""
        try:
            projects = self.client.get_projects()
            return [
                {
                    "id": p.get("id"),
                    "name": p.get("name", "")
                }
                for p in projects
            ]
        except SquashClientError:
            return []

    def find_best_match(
        self,
        robot_test_name: str,
        squash_test_cases: List[Dict[str, Any]],
        threshold: float = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best matching Squash test case for a Robot test name.

        Args:
            robot_test_name: Name of the Robot Framework test
            squash_test_cases: List of Squash test cases to search
            threshold: Minimum similarity score (default: 0.6)

        Returns:
            Best match with score, or None if no match above threshold
        """
        threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD
        best_match = None
        best_score = 0

        for tc in squash_test_cases:
            squash_name = tc.get("name", "")
            score = self._calculate_similarity(robot_test_name, squash_name)

            if score > best_score and score >= threshold:
                best_score = score
                best_match = {
                    "squash_test_case_id": tc["id"],
                    "squash_test_case_name": squash_name,
                    "score": round(score, 3),
                    "confidence": self._score_to_confidence(score)
                }

        return best_match

    def _score_to_confidence(self, score: float) -> str:
        """Convert similarity score to confidence level."""
        if score >= 0.9:
            return "high"
        elif score >= 0.75:
            return "medium"
        else:
            return "low"

    def auto_link_tests(
        self,
        robot_test_cases: List[Dict[str, Any]],
        squash_project_id: int = None,
        threshold: float = None,
        skip_already_mapped: bool = True
    ) -> Dict[str, Any]:
        """
        Automatically find matches for Robot tests from Squash test cases.

        Args:
            robot_test_cases: List of Robot test cases (with 'name' field)
            squash_project_id: Optional Squash project to filter test cases
            threshold: Minimum similarity score
            skip_already_mapped: Skip tests that already have a mapping

        Returns:
            Dictionary with matches and statistics
        """
        # Fetch all Squash test cases
        squash_test_cases = self.fetch_squash_test_cases(squash_project_id)

        if not squash_test_cases:
            return {
                "success": False,
                "error": "Could not fetch test cases from Squash TM",
                "matches": [],
                "stats": {}
            }

        matches = []
        matched_count = 0
        skipped_count = 0
        no_match_count = 0

        for robot_tc in robot_test_cases:
            robot_name = robot_tc.get("name", "")
            existing_mapping = robot_tc.get("squash_test_case_id")

            # Skip if already mapped and flag is set
            if skip_already_mapped and existing_mapping:
                skipped_count += 1
                matches.append({
                    "robot_test_name": robot_name,
                    "status": "skipped",
                    "existing_mapping": existing_mapping,
                    "match": None
                })
                continue

            # Find best match
            match = self.find_best_match(robot_name, squash_test_cases, threshold)

            if match:
                matched_count += 1
                matches.append({
                    "robot_test_name": robot_name,
                    "status": "matched",
                    "existing_mapping": existing_mapping,
                    "match": match
                })
            else:
                no_match_count += 1
                matches.append({
                    "robot_test_name": robot_name,
                    "status": "no_match",
                    "existing_mapping": existing_mapping,
                    "match": None
                })

        return {
            "success": True,
            "matches": matches,
            "stats": {
                "total": len(robot_test_cases),
                "matched": matched_count,
                "skipped": skipped_count,
                "no_match": no_match_count,
                "squash_test_cases_available": len(squash_test_cases)
            }
        }

    def find_matching_campaign(
        self,
        project_name: str,
        squash_project_id: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a Squash campaign that matches the project name.

        Args:
            project_name: Name of the Robot project
            squash_project_id: Optional Squash project to filter campaigns

        Returns:
            Best matching campaign or None
        """
        campaigns = self.fetch_squash_campaigns(squash_project_id)

        best_match = None
        best_score = 0

        for campaign in campaigns:
            score = self._calculate_similarity(project_name, campaign["name"])
            if score > best_score and score >= self.DEFAULT_THRESHOLD:
                best_score = score
                best_match = {
                    "id": campaign["id"],
                    "name": campaign["name"],
                    "score": round(score, 3)
                }

        return best_match
