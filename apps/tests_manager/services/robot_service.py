"""Robot Framework execution service."""
import subprocess
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from django.conf import settings
from core.exceptions import RobotExecutionError


class RobotService:
    """
    Service for executing Robot Framework tests and parsing results.
    """

    def __init__(self, output_dir: Path = None):
        """
        Initialize the Robot service.

        Args:
            output_dir: Directory for Robot Framework output files
        """
        self.output_dir = output_dir or settings.ROBOT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def scan_directory(self, directory: str) -> List[str]:
        """
        Scan a directory for Robot Framework test names.

        Args:
            directory: Path to directory containing .robot files

        Returns:
            List of test names found in the directory
        """
        test_names = []
        dir_path = Path(directory)

        if not dir_path.exists():
            raise RobotExecutionError(f"Directory not found: {directory}")

        if not dir_path.is_dir():
            raise RobotExecutionError(f"Path is not a directory: {directory}")

        # Find all .robot files
        robot_files = list(dir_path.glob('**/*.robot'))

        if not robot_files:
            raise RobotExecutionError(f"No .robot files found in: {directory}")

        for robot_file in robot_files:
            try:
                tests = self._extract_test_names(robot_file)
                test_names.extend(tests)
            except Exception as e:
                # Skip files that can't be parsed
                pass

        return sorted(set(test_names))

    def _extract_test_names(self, robot_file: Path) -> List[str]:
        """
        Extract test names from a Robot Framework file.

        Args:
            robot_file: Path to .robot file

        Returns:
            List of test names
        """
        test_names = []
        in_test_cases_section = False

        with open(robot_file, 'r', encoding='utf-8') as f:
            for line in f:
                line_stripped = line.strip()

                # Check for Test Cases section
                if line_stripped.lower().startswith('*** test cases ***'):
                    in_test_cases_section = True
                    continue

                # Check for end of section
                if line_stripped.startswith('***'):
                    in_test_cases_section = False
                    continue

                # If in test cases section and line starts without indentation
                if in_test_cases_section and line and not line[0].isspace():
                    test_name = line_stripped
                    # Skip empty lines and comments
                    if test_name and not test_name.startswith('#'):
                        test_names.append(test_name)

        return test_names

    def execute(
        self,
        directory: str,
        suite_id: str,
        variables: Dict[str, str] = None
    ) -> Dict:
        """
        Execute Robot Framework tests in a directory.

        Args:
            directory: Path to directory containing .robot files
            suite_id: ID of the test suite (for output file naming)
            variables: Optional variables to pass to Robot

        Returns:
            Dict with execution results including parsed test results
        """
        dir_path = Path(directory)

        if not dir_path.exists():
            raise RobotExecutionError(f"Directory not found: {directory}")

        # Create unique output directory for this execution
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        execution_output_dir = self.output_dir / f"{suite_id}_{timestamp}"
        execution_output_dir.mkdir(parents=True, exist_ok=True)

        output_xml = execution_output_dir / 'output.xml'
        log_html = execution_output_dir / 'log.html'
        report_html = execution_output_dir / 'report.html'

        # Build command
        cmd = [
            'robot',
            '--outputdir', str(execution_output_dir),
            '--output', 'output.xml',
            '--log', 'log.html',
            '--report', 'report.html',
        ]

        # Add variables if provided
        if variables:
            for key, value in variables.items():
                cmd.extend(['--variable', f'{key}:{value}'])

        cmd.append(str(dir_path))

        # Execute Robot Framework
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
                cwd=str(dir_path.parent)
            )

            # Parse results from output.xml
            test_results = []
            summary = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}

            if output_xml.exists():
                test_results, summary = self._parse_output_xml(output_xml)

            return {
                'success': result.returncode == 0,
                'return_code': result.returncode,
                'output_dir': str(execution_output_dir),
                'output_xml': str(output_xml),
                'log_html': str(log_html),
                'report_html': str(report_html),
                'stdout': result.stdout,
                'stderr': result.stderr,
                'test_results': test_results,
                'summary': summary,
            }

        except subprocess.TimeoutExpired:
            raise RobotExecutionError("Test execution timed out after 1 hour")
        except FileNotFoundError:
            raise RobotExecutionError(
                "Robot Framework not found. Make sure it's installed: pip install robotframework"
            )
        except Exception as e:
            raise RobotExecutionError(f"Execution failed: {str(e)}")

    def _parse_output_xml(self, output_xml: Path) -> tuple:
        """
        Parse Robot Framework output.xml file.

        Args:
            output_xml: Path to output.xml

        Returns:
            Tuple of (test_results list, summary dict)
        """
        test_results = []
        summary = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}

        try:
            tree = ET.parse(output_xml)
            root = tree.getroot()

            # Find all test elements
            for test in root.iter('test'):
                test_name = test.get('name', 'Unknown')
                status_elem = test.find('status')

                if status_elem is not None:
                    status = status_elem.get('status', 'FAIL')
                    message = status_elem.text or ''

                    test_results.append({
                        'name': test_name,
                        'status': status,
                        'message': message,
                        'start_time': status_elem.get('starttime', ''),
                        'end_time': status_elem.get('endtime', ''),
                    })

                    summary['total'] += 1
                    if status == 'PASS':
                        summary['passed'] += 1
                    elif status == 'FAIL':
                        summary['failed'] += 1
                    elif status == 'SKIP':
                        summary['skipped'] += 1

            # Also get statistics from statistics element if available
            statistics = root.find('.//statistics/total/stat')
            if statistics is not None:
                summary['total'] = int(statistics.get('pass', 0)) + int(statistics.get('fail', 0))
                summary['passed'] = int(statistics.get('pass', 0))
                summary['failed'] = int(statistics.get('fail', 0))

        except ET.ParseError as e:
            raise RobotExecutionError(f"Failed to parse output.xml: {e}")

        return test_results, summary

    def get_execution_report_url(self, output_dir: str) -> Optional[str]:
        """
        Get the URL path for an execution's report.

        Args:
            output_dir: Path to the execution output directory

        Returns:
            URL path to the report, or None if not found
        """
        report_path = Path(output_dir) / 'report.html'
        if report_path.exists():
            # Return relative path from ROBOT_OUTPUT_DIR
            try:
                rel_path = report_path.relative_to(self.output_dir)
                return f'/robot-output/{rel_path}'
            except ValueError:
                return None
        return None
