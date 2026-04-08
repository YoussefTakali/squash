"""
Robot Framework Listener for Squash TM Integration.

This listener syncs test results to Squash TM in real-time as each test completes.

Usage:
    robot --listener squash_listener.py:config.json tests/
    
Config file format (config.json):
{
    "squash_url": "https://squash.example.com",
    "token": "your-api-token",
    "iteration_id": 123,
    "mappings": {
        "Test Case Name": 456,
        "Another Test": 789
    }
}
"""
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("[SquashListener] Warning: requests module not installed")
    requests = None


class SquashListener:
    """Robot Framework listener that syncs test results to Squash TM."""

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, config_file: str):
        """
        Initialize the listener with configuration.
        
        Args:
            config_file: Path to JSON config file with Squash credentials and mappings
        """
        self.config = self._load_config(config_file)
        self.squash_url = self.config.get("squash_url", "")
        self.token = self.config.get("token", "")
        self.iteration_id = self.config.get("iteration_id")
        self.mappings = self.config.get("mappings", {})
        
        # Track results for summary
        self.results = []
        
        if not self.squash_url or not self.token:
            print("[SquashListener] Warning: Squash credentials not configured")
        
        if not self.iteration_id:
            print("[SquashListener] Warning: iteration_id not configured")
        
        print(f"[SquashListener] Initialized with {len(self.mappings)} test mappings")

    def _load_config(self, config_file: str) -> dict:
        """Load configuration from JSON file."""
        try:
            config_path = Path(config_file)
            if not config_path.exists():
                print(f"[SquashListener] Config file not found: {config_file}")
                return {}
            
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"[SquashListener] Invalid JSON in config: {e}")
            return {}
        except Exception as e:
            print(f"[SquashListener] Error loading config: {e}")
            return {}

    def start_suite(self, data, result):
        """Called when a test suite starts."""
        print(f"[SquashListener] Starting suite: {data.name}")

    def end_suite(self, data, result):
        """Called when a test suite ends."""
        print(f"[SquashListener] Suite finished: {data.name} - {result.status}")

    def start_test(self, data, result):
        """Called when a test starts."""
        test_name = data.name
        squash_id = self.mappings.get(test_name)
        
        if squash_id:
            print(f"[SquashListener] Starting test: {test_name} (Squash ID: {squash_id})")
            # Optionally update status to RUNNING
            # self._update_squash(squash_id, "RUNNING")
        else:
            print(f"[SquashListener] Starting test: {test_name} (no Squash mapping)")

    def end_test(self, data, result):
        """Called when a test ends - this is where we sync to Squash."""
        test_name = data.name
        squash_id = self.mappings.get(test_name)
        
        # Map Robot Framework status to Squash status
        if result.passed:
            status = "SUCCESS"
        else:
            status = "FAILURE"
        
        # Store result for logging
        self.results.append({
            "name": test_name,
            "status": status,
            "squash_id": squash_id,
            "message": result.message if hasattr(result, "message") else None
        })
        
        if not squash_id:
            print(f"[SquashListener] Test finished: {test_name} - {status} (no Squash mapping)")
            return
        
        print(f"[SquashListener] Test finished: {test_name} - {status}")
        
        # Sync to Squash
        success = self._update_squash(squash_id, status, result.message if hasattr(result, "message") else None)
        
        if success:
            print(f"[SquashListener] Synced to Squash: Test Case #{squash_id} -> {status}")
        else:
            print(f"[SquashListener] Failed to sync to Squash: Test Case #{squash_id}")

    def _update_squash(self, test_plan_item_id: int, status: str, comment: str = None) -> bool:
        """
        Update test execution status in Squash TM.
        
        Args:
            test_plan_item_id: The test plan item ID in Squash
            status: Execution status (SUCCESS, FAILURE, BLOCKED, etc.)
            comment: Optional comment (e.g., failure message)
        
        Returns:
            True if successful, False otherwise
        """
        if not requests:
            print("[SquashListener] Cannot sync: requests module not available")
            return False
        
        if not self.squash_url or not self.token or not self.iteration_id:
            return False
        
        try:
            # Build API URL
            base_url = self.squash_url.rstrip("/")
            if not base_url.endswith("/api/rest/latest"):
                base_url = f"{base_url}/api/rest/latest"
            
            # Create a new execution
            url = f"{base_url}/iterations/{self.iteration_id}/test-plan/{test_plan_item_id}/executions"
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            data = {"execution_status": status}
            if comment:
                data["comment"] = comment[:2000]  # Truncate long messages
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.ok:
                return True
            else:
                print(f"[SquashListener] API error: {response.status_code} - {response.text[:200]}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"[SquashListener] Request error: {e}")
            return False
        except Exception as e:
            print(f"[SquashListener] Unexpected error: {e}")
            return False

    def close(self):
        """Called when the listener is closed (end of execution)."""
        print("\n[SquashListener] === Execution Summary ===")
        
        passed = sum(1 for r in self.results if r["status"] == "SUCCESS")
        failed = sum(1 for r in self.results if r["status"] == "FAILURE")
        mapped = sum(1 for r in self.results if r["squash_id"])
        
        print(f"Total tests: {len(self.results)}")
        print(f"Passed: {passed}, Failed: {failed}")
        print(f"Synced to Squash: {mapped}")
        print("[SquashListener] ========================\n")
