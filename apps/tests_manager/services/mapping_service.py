"""Mapping service for Robot Framework to Squash TM."""
from typing import List, Dict, Optional

from apps.tests_manager.repositories.json_repository import JsonTestSuiteRepository
from apps.squash.services.squash_service import SquashService


class MappingService:
    """
    Service for managing mappings between Robot Framework tests
    and Squash TM test cases, and syncing results.
    """

    def __init__(self, suite_repo: JsonTestSuiteRepository = None):
        """
        Initialize the mapping service.

        Args:
            suite_repo: Test suite repository
        """
        self.suite_repo = suite_repo or JsonTestSuiteRepository()

    def get_suite_mappings(self, suite_id: str) -> List[Dict]:
        """
        Get current mappings for a test suite.

        Args:
            suite_id: Test suite ID

        Returns:
            List of mappings [{robot_test_name, squash_test_case_id}, ...]
        """
        suite = self.suite_repo.get_by_id(suite_id)
        if not suite:
            return []
        return suite.get('test_mappings', [])

    def update_mappings(self, suite_id: str, mappings: List[Dict]) -> bool:
        """
        Update mappings for a test suite.

        Args:
            suite_id: Test suite ID
            mappings: List of mappings

        Returns:
            True if successful
        """
        result = self.suite_repo.update_mappings(suite_id, mappings)
        return result is not None

    def get_unmapped_tests(self, suite_id: str) -> List[str]:
        """
        Get tests that don't have Squash mappings.

        Args:
            suite_id: Test suite ID

        Returns:
            List of unmapped test names
        """
        suite = self.suite_repo.get_by_id(suite_id)
        if not suite:
            return []

        detected_tests = set(suite.get('detected_tests', []))
        mapped_tests = {m['robot_test_name'] for m in suite.get('test_mappings', [])}

        return sorted(detected_tests - mapped_tests)

    def sync_to_squash(
        self,
        suite_id: str,
        test_results: List[Dict],
        squash_url: str,
        squash_token: str
    ) -> Dict:
        """
        Sync Robot Framework results to Squash TM.

        Args:
            suite_id: Test suite ID
            test_results: Robot Framework test results
            squash_url: Squash API URL
            squash_token: Squash API token

        Returns:
            Dict with sync results and summary
        """
        suite = self.suite_repo.get_by_id(suite_id)
        if not suite:
            return {
                'success': False,
                'error': 'Test suite not found',
                'results': []
            }

        iteration_id = suite.get('squash_iteration_id')
        if not iteration_id:
            return {
                'success': False,
                'error': 'No Squash iteration configured for this suite',
                'results': []
            }

        mappings = suite.get('test_mappings', [])
        if not mappings:
            return {
                'success': False,
                'error': 'No test mappings configured',
                'results': []
            }

        # Use Squash service to sync results
        squash_service = SquashService(squash_url, squash_token)

        try:
            sync_results = squash_service.sync_robot_results(
                iteration_id=iteration_id,
                test_results=test_results,
                test_mappings=mappings
            )

            # Calculate summary
            successful = sum(1 for r in sync_results if r.get('success'))
            failed = len(sync_results) - successful

            return {
                'success': failed == 0,
                'results': sync_results,
                'summary': {
                    'total': len(sync_results),
                    'synced': successful,
                    'failed': failed
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

    def auto_map_tests(
        self,
        suite_id: str,
        squash_url: str,
        squash_token: str,
        project_id: int
    ) -> Dict:
        """
        Attempt to automatically map tests by matching names.

        Args:
            suite_id: Test suite ID
            squash_url: Squash API URL
            squash_token: Squash API token
            project_id: Squash project ID to search in

        Returns:
            Dict with auto-mapping results
        """
        suite = self.suite_repo.get_by_id(suite_id)
        if not suite:
            return {'success': False, 'error': 'Suite not found', 'mappings': []}

        detected_tests = suite.get('detected_tests', [])
        if not detected_tests:
            return {'success': False, 'error': 'No tests detected', 'mappings': []}

        from apps.squash.client import SquashClient
        client = SquashClient(squash_url, squash_token)

        new_mappings = []
        for test_name in detected_tests:
            try:
                # Search for test cases with similar name
                results = client.search_test_cases(project_id, name=test_name)
                if results:
                    # Use the first match
                    new_mappings.append({
                        'robot_test_name': test_name,
                        'squash_test_case_id': results[0]['id'],
                        'auto_mapped': True
                    })
            except Exception:
                continue

        if new_mappings:
            # Merge with existing mappings
            existing = {m['robot_test_name']: m for m in suite.get('test_mappings', [])}
            for mapping in new_mappings:
                if mapping['robot_test_name'] not in existing:
                    existing[mapping['robot_test_name']] = mapping

            self.suite_repo.update_mappings(suite_id, list(existing.values()))

        return {
            'success': True,
            'mappings': new_mappings,
            'count': len(new_mappings)
        }
