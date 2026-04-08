"""Squash TM API Client."""
import math
import os
import requests
from typing import Optional, List, Dict, Any


class SquashClientError(Exception):
    """Exception raised for Squash API errors."""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class SquashClient:
    """
    Client for interacting with Squash TM REST API.
    
    API Documentation: https://squash-tm.org/documentation/api/
    """

    def __init__(self, base_url: str, token: str):
        """
        Initialize the Squash client.
        
        Args:
            base_url: Base URL of Squash TM instance (e.g., https://squash.example.com)
            token: API authentication token
        """
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/api/rest/latest"):
            self.base_url = f"{self.base_url}/api/rest/latest"
        
        # SSL verification from environment
        verify_ssl = os.environ.get("SQUASH_VERIFY_SSL", "true").lower()
        self.verify_ssl = verify_ssl not in ("false", "0", "no")
        
        # Proxy settings from environment
        self.proxies = {}
        http_proxy = os.environ.get("HTTP_PROXY")
        https_proxy = os.environ.get("HTTPS_PROXY")
        if http_proxy:
            self.proxies["http"] = http_proxy
        if https_proxy:
            self.proxies["https"] = https_proxy
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        self.session.verify = self.verify_ssl
        if self.proxies:
            self.session.proxies.update(self.proxies)

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an API request."""
        url = f"{self.base_url}/{endpoint.lstrip("/")}"
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            if response.status_code == 401:
                raise SquashClientError("Invalid or expired token", status_code=401)
            
            if response.status_code == 403:
                raise SquashClientError("Permission denied", status_code=403)
            
            if response.status_code == 404:
                raise SquashClientError("Resource not found", status_code=404)
            
            if not response.ok:
                error_msg = response.text or f"HTTP {response.status_code}"
                raise SquashClientError(error_msg, status_code=response.status_code)
            
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.ConnectionError as e:
            raise SquashClientError(f"Connection error: {str(e)}")
        except requests.exceptions.Timeout:
            raise SquashClientError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise SquashClientError(f"Request failed: {str(e)}")

    def _get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self._request("GET", endpoint, **kwargs)

    def _post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self._request("POST", endpoint, **kwargs)

    def _put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self._request("PUT", endpoint, **kwargs)

    def _patch(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self._request("PATCH", endpoint, **kwargs)

    # Authentication
    def validate_token(self) -> bool:
        """Validate the API token by making a test request."""
        try:
            self._get("projects")
            return True
        except SquashClientError as e:
            if e.status_code in (401, 403):
                return False
            raise

    # Projects
    def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects."""
        response = self._get("projects")
        return response.get("_embedded", {}).get("projects", [])

    def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get a specific project."""
        return self._get(f"projects/{project_id}")

    # Campaigns
    def get_campaigns(self, project_id: int = None) -> List[Dict[str, Any]]:
        """Get all campaigns, optionally filtered by project."""
        endpoint = f"projects/{project_id}/campaigns" if project_id else "campaigns"
        response = self._get(endpoint)
        return response.get("_embedded", {}).get("campaigns", [])

    def get_campaign(self, campaign_id: int) -> Dict[str, Any]:
        """Get a specific campaign."""
        return self._get(f"campaigns/{campaign_id}")

    # Campaign Folders
    def get_campaign_folders_page(self, page: int = 0, size: int = 2000) -> Dict[str, Any]:
        """
        Get a single page of campaign folders.
        
        Args:
            page: Page number (0-indexed)
            size: Number of items per page (max 2000)
            
        Returns:
            Response containing page info and campaign folders
        """
        params = {"page": page, "size": min(size, 2000)}
        return self._get("campaign-folders", params=params)

    def get_all_campaign_folders(self) -> List[Dict[str, Any]]:
        """
        Get all campaign folders using pagination.
        
        First fetches without query params to get total count,
        then calculates pages needed and fetches all.
        
        Returns:
            List of all campaign folders
        """
        MAX_PAGE_SIZE = 2000
        
        # First request to get total count
        first_response = self._get("campaign-folders")
        
        # Get total elements from page info
        page_info = first_response.get("page", {})
        total_elements = page_info.get("totalElements", 0)
        
        if total_elements == 0:
            return first_response.get("_embedded", {}).get("campaign-folders", [])
        
        # Calculate number of pages needed
        total_pages = math.ceil(total_elements / MAX_PAGE_SIZE)
        
        all_folders = []
        
        # Fetch all pages
        for page_num in range(total_pages):
            response = self.get_campaign_folders_page(page=page_num, size=MAX_PAGE_SIZE)
            folders = response.get("_embedded", {}).get("campaign-folders", [])
            all_folders.extend(folders)
        
        return all_folders

    def find_campaign_folder_by_name(self, folder_name: str) -> Optional[Dict[str, Any]]:
        """
        Search for a campaign folder by name.
        
        Args:
            folder_name: Name of the campaign folder to find
            
        Returns:
            Campaign folder or None if not found
        """
        all_folders = self.get_all_campaign_folders()
        
        for folder in all_folders:
            if folder.get("name") == folder_name:
                return folder
        
        return None

    def get_campaign_folder_content(self, folder_id: int) -> Dict[str, Any]:
        """
        Get the content of a campaign folder (subfolders and campaigns).
        
        Args:
            folder_id: ID of the campaign folder
            
        Returns:
            Folder content with subfolders and campaigns
        """
        return self._get(f"campaign-folders/{folder_id}/content")

    def _get_embedded_list(self, response: Dict[str, Any], keys: List[str]) -> List[Dict[str, Any]]:
        """Read a list from `_embedded`, handling key naming variations."""
        embedded = response.get("_embedded", {})

        for key in keys:
            value = embedded.get(key)
            if isinstance(value, list):
                return value

        normalized_keys = {k.replace("-", "").replace("_", "").lower() for k in keys}
        for embedded_key, value in embedded.items():
            if not isinstance(value, list):
                continue
            normalized_embedded_key = embedded_key.replace("-", "").replace("_", "").lower()
            if normalized_embedded_key in normalized_keys:
                return value

        return []

    def _extract_test_case_reference(self, test_plan_item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract referenced test case payload from a test-plan item."""
        for key in (
            "referenced_test_case",
            "referenced-test-case",
            "referencedTestCase",
            "test_case",
            "test-case",
            "testCase",
        ):
            value = test_plan_item.get(key)
            if isinstance(value, dict) and value:
                return value
        return {}

    def _extract_test_case_id(self, test_plan_item: Dict[str, Any], referenced_tc: Dict[str, Any]) -> Optional[int]:
        """Extract referenced test-case ID from a test-plan item."""
        tc_id = referenced_tc.get("id")
        if tc_id:
            return tc_id

        for key in ("test_case_id", "test-case-id", "testCaseId", "referenced_test_case_id"):
            value = test_plan_item.get(key)
            if value:
                return value

        referenced_link = test_plan_item.get("_links", {}).get("referenced_test_case", {})
        href = referenced_link.get("href", "")
        if "/test-cases/" in href:
            try:
                return int(href.rstrip("/").split("/")[-1])
            except (TypeError, ValueError):
                return None

        return None

    def get_all_test_cases_under_campaign_folder(self, folder_id: int) -> List[Dict[str, Any]]:
        """
        Recursively get all test cases under a campaign folder.
        
        Traverses all subfolders and campaigns to collect every test case.
        
        Args:
            folder_id: ID of the campaign folder
            
        Returns:
            List of all test cases under the folder (including nested)
        """
        test_cases_by_id: Dict[int, Dict[str, Any]] = {}
        visited_folders = set()

        def collect_from_folder(current_folder_id: int) -> None:
            if current_folder_id in visited_folders:
                return
            visited_folders.add(current_folder_id)

            try:
                content = self.get_campaign_folder_content(current_folder_id)
            except SquashClientError:
                return

            # Recursively process nested campaign folders first.
            subfolders = self._get_embedded_list(
                content, ["campaign-folders", "campaign_folders", "campaignFolders", "folders"]
            )

            if subfolders:
                for subfolder in subfolders:
                    subfolder_id = subfolder.get("id")
                    if subfolder_id:
                        collect_from_folder(subfolder_id)
                return

            # Leaf folder: process campaigns, then iterations, then test cases.
            campaigns = self._get_embedded_list(content, ["campaigns"])
            for campaign in campaigns:
                campaign_id = campaign.get("id")
                if not campaign_id:
                    continue

                try:
                    iterations = self.get_iterations(campaign_id)
                except SquashClientError:
                    continue

                for iteration in iterations:
                    iteration_id = iteration.get("id")
                    if not iteration_id:
                        continue

                    try:
                        test_plan_items = self.get_iteration_test_plan(iteration_id)
                    except SquashClientError:
                        continue

                    for item in test_plan_items:
                        referenced_tc = self._extract_test_case_reference(item)
                        tc_id = self._extract_test_case_id(item, referenced_tc)
                        if not tc_id:
                            continue

                        if tc_id in test_cases_by_id:
                            continue

                        # Keep full test case payload when accessible, otherwise keep reference.
                        try:
                            test_cases_by_id[tc_id] = self.get_test_case(tc_id)
                        except SquashClientError:
                            test_cases_by_id[tc_id] = referenced_tc

        collect_from_folder(folder_id)
        return list(test_cases_by_id.values())

    # Iterations
    def get_iterations(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get all iterations in a campaign."""
        response = self._get(f"campaigns/{campaign_id}/iterations")
        return self._get_embedded_list(response, ["iterations"])

    def get_iteration(self, iteration_id: int) -> Dict[str, Any]:
        """Get a specific iteration."""
        return self._get(f"iterations/{iteration_id}")

    def get_iteration_test_plan(self, iteration_id: int) -> List[Dict[str, Any]]:
        """Get test plan items for an iteration."""
        response = self._get(f"iterations/{iteration_id}/test-plan")
        return self._get_embedded_list(
            response,
            ["test-plan", "test_plan", "testPlan", "test-plan-items", "testPlanItems"],
        )

    # Test Cases
    def get_test_cases(self, project_id: int = None) -> List[Dict[str, Any]]:
        """Get all test cases, optionally filtered by project."""
        endpoint = f"projects/{project_id}/test-cases" if project_id else "test-cases"
        response = self._get(endpoint)
        return response.get("_embedded", {}).get("test-cases", [])

    def get_test_case(self, test_case_id: int) -> Dict[str, Any]:
        """Get a specific test case."""
        return self._get(f"test-cases/{test_case_id}")

    # Executions
    def create_execution(self, iteration_id: int, test_plan_item_id: int, status: str = "UNTESTABLE") -> Dict[str, Any]:
        """Create a new execution for a test plan item."""
        return self._post(
            f"iterations/{iteration_id}/test-plan/{test_plan_item_id}/executions",
            json={"execution_status": status}
        )

    def update_execution_status(self, execution_id: int, status: str, comment: str = None) -> Dict[str, Any]:
        """Update the status of an execution."""
        data = {"execution_status": status}
        if comment:
            data["comment"] = comment
        return self._patch(f"executions/{execution_id}", json=data)

    def create_and_update_execution(self, iteration_id: int, test_plan_item_id: int, status: str, comment: str = None) -> Dict[str, Any]:
        """Create a new execution and set its status."""
        execution = self.create_execution(iteration_id, test_plan_item_id)
        execution_id = execution.get("id")
        if execution_id and status:
            return self.update_execution_status(execution_id, status, comment)
        return execution
