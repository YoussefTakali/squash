"""Views for test suite manager."""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from core.decorators import login_required_json, squash_token_required
from apps.tests_manager.forms import TestSuiteForm
from apps.tests_manager.repositories.json_repository import (
    JsonTestSuiteRepository,
    JsonExecutionRepository
)
from apps.tests_manager.services.robot_service import RobotService
from apps.tests_manager.services.mapping_service import MappingService
from core.exceptions import RobotExecutionError


def get_suite_or_404(suite_id: str, user_id: str):
    """Get suite by ID, checking ownership."""
    repo = JsonTestSuiteRepository()
    suite = repo.get_by_id(suite_id)
    if not suite or suite.get('user_id') != user_id:
        return None
    return suite


@login_required_json
def suite_list(request):
    """List all test suites for the current user."""
    user = request.current_user
    if not user:
        return redirect('accounts:login')

    repo = JsonTestSuiteRepository()
    suites = repo.get_by_user(user['id'])

    return render(request, 'tests/suite_list.html', {
        'suites': suites,
        'user': user,
    })


@login_required_json
def suite_create(request):
    """Create a new test suite."""
    user = request.current_user
    if not user:
        return redirect('accounts:login')

    if request.method == 'POST':
        form = TestSuiteForm(request.POST)
        if form.is_valid():
            repo = JsonTestSuiteRepository()
            suite = repo.save({
                'name': form.cleaned_data['name'],
                'robot_directory': form.cleaned_data['robot_directory'],
                'squash_iteration_id': form.cleaned_data.get('squash_iteration_id'),
                'squash_campaign_id': form.cleaned_data.get('squash_campaign_id'),
                'user_id': user['id'],
                'test_mappings': [],
                'detected_tests': [],
            })
            messages.success(request, f'Test suite "{suite["name"]}" created successfully!')
            return redirect('tests_manager:suite_detail', suite_id=suite['id'])
    else:
        form = TestSuiteForm()

    return render(request, 'tests/suite_create.html', {'form': form})


@login_required_json
def suite_detail(request, suite_id):
    """View test suite details."""
    user = request.current_user
    if not user:
        return redirect('accounts:login')

    suite = get_suite_or_404(suite_id, user['id'])
    if not suite:
        messages.error(request, 'Test suite not found.')
        return redirect('tests_manager:suite_list')

    # Get recent executions
    exec_repo = JsonExecutionRepository()
    executions = exec_repo.get_by_suite(suite_id, limit=5)

    # Prepare mapping data
    detected_tests = suite.get('detected_tests', [])
    mappings = {m['robot_test_name']: m for m in suite.get('test_mappings', [])}

    mapping_data = []
    for test_name in detected_tests:
        mapping = mappings.get(test_name, {})
        mapping_data.append({
            'robot_test_name': test_name,
            'squash_test_case_id': mapping.get('squash_test_case_id', ''),
        })

    return render(request, 'tests/suite_detail.html', {
        'suite': suite,
        'executions': executions,
        'mapping_data': mapping_data,
        'has_squash_token': bool(user.get('squash_token')),
    })


@login_required_json
def suite_edit(request, suite_id):
    """Edit a test suite."""
    user = request.current_user
    if not user:
        return redirect('accounts:login')

    suite = get_suite_or_404(suite_id, user['id'])
    if not suite:
        messages.error(request, 'Test suite not found.')
        return redirect('tests_manager:suite_list')

    if request.method == 'POST':
        form = TestSuiteForm(request.POST)
        if form.is_valid():
            repo = JsonTestSuiteRepository()
            suite['name'] = form.cleaned_data['name']
            suite['robot_directory'] = form.cleaned_data['robot_directory']
            suite['squash_iteration_id'] = form.cleaned_data.get('squash_iteration_id')
            suite['squash_campaign_id'] = form.cleaned_data.get('squash_campaign_id')
            repo.save(suite)
            messages.success(request, 'Test suite updated successfully!')
            return redirect('tests_manager:suite_detail', suite_id=suite_id)
    else:
        form = TestSuiteForm(initial={
            'name': suite['name'],
            'robot_directory': suite['robot_directory'],
            'squash_iteration_id': suite.get('squash_iteration_id'),
            'squash_campaign_id': suite.get('squash_campaign_id'),
        })

    return render(request, 'tests/suite_edit.html', {'form': form, 'suite': suite})


@login_required_json
@require_http_methods(["POST"])
def suite_delete(request, suite_id):
    """Delete a test suite."""
    user = request.current_user
    if not user:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    suite = get_suite_or_404(suite_id, user['id'])
    if not suite:
        return JsonResponse({'error': 'Suite not found'}, status=404)

    repo = JsonTestSuiteRepository()
    repo.delete(suite_id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'redirect': '/suites/'})

    messages.success(request, 'Test suite deleted.')
    return redirect('tests_manager:suite_list')


@login_required_json
@require_http_methods(["POST"])
def suite_scan(request, suite_id):
    """Scan directory for Robot Framework tests."""
    user = request.current_user
    if not user:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    suite = get_suite_or_404(suite_id, user['id'])
    if not suite:
        return JsonResponse({'error': 'Suite not found'}, status=404)

    robot_service = RobotService()

    try:
        tests = robot_service.scan_directory(suite['robot_directory'])

        # Update suite with detected tests
        repo = JsonTestSuiteRepository()
        repo.update_detected_tests(suite_id, tests)

        return JsonResponse({
            'success': True,
            'tests': tests,
            'count': len(tests)
        })
    except RobotExecutionError as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required_json
@require_http_methods(["POST"])
def suite_execute(request, suite_id):
    """Execute Robot Framework tests."""
    user = request.current_user
    if not user:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    suite = get_suite_or_404(suite_id, user['id'])
    if not suite:
        return JsonResponse({'error': 'Suite not found'}, status=404)

    robot_service = RobotService()
    exec_repo = JsonExecutionRepository()

    try:
        # Execute tests
        result = robot_service.execute(
            directory=suite['robot_directory'],
            suite_id=suite_id
        )

        # Save execution record
        execution = exec_repo.save({
            'suite_id': suite_id,
            'status': 'PASSED' if result['success'] else 'FAILED',
            'output_dir': result['output_dir'],
            'test_results': result['test_results'],
            'summary': result['summary'],
            'squash_synced': False,
        })

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'execution_id': execution['id'],
                'summary': result['summary'],
                'redirect': f'/suites/{suite_id}/results/{execution["id"]}/'
            })

        messages.success(
            request,
            f'Tests executed: {result["summary"]["passed"]} passed, {result["summary"]["failed"]} failed'
        )
        return redirect('tests_manager:execution_results', suite_id=suite_id, execution_id=execution['id'])

    except RobotExecutionError as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': str(e)}, status=400)
        messages.error(request, f'Execution failed: {str(e)}')
        return redirect('tests_manager:suite_detail', suite_id=suite_id)


@login_required_json
@require_http_methods(["POST"])
def suite_mappings(request, suite_id):
    """Save test mappings."""
    user = request.current_user
    if not user:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    suite = get_suite_or_404(suite_id, user['id'])
    if not suite:
        return JsonResponse({'error': 'Suite not found'}, status=404)

    try:
        data = json.loads(request.body)
        mappings = data.get('mappings', [])

        # Validate mappings
        valid_mappings = []
        for mapping in mappings:
            if mapping.get('robot_test_name') and mapping.get('squash_test_case_id'):
                valid_mappings.append({
                    'robot_test_name': mapping['robot_test_name'],
                    'squash_test_case_id': int(mapping['squash_test_case_id'])
                })

        mapping_service = MappingService()
        mapping_service.update_mappings(suite_id, valid_mappings)

        return JsonResponse({
            'success': True,
            'count': len(valid_mappings)
        })

    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error': f'Invalid data: {str(e)}'}, status=400)


@login_required_json
def execution_results(request, suite_id, execution_id):
    """View execution results."""
    user = request.current_user
    if not user:
        return redirect('accounts:login')

    suite = get_suite_or_404(suite_id, user['id'])
    if not suite:
        messages.error(request, 'Test suite not found.')
        return redirect('tests_manager:suite_list')

    exec_repo = JsonExecutionRepository()
    execution = exec_repo.get_by_id(execution_id)

    if not execution or execution.get('suite_id') != suite_id:
        messages.error(request, 'Execution not found.')
        return redirect('tests_manager:suite_detail', suite_id=suite_id)

    # Get mappings for showing sync status
    mappings = {m['robot_test_name']: m for m in suite.get('test_mappings', [])}

    # Enhance test results with mapping info
    enhanced_results = []
    for result in execution.get('test_results', []):
        mapping = mappings.get(result['name'])
        enhanced_results.append({
            **result,
            'has_mapping': mapping is not None,
            'squash_id': mapping.get('squash_test_case_id') if mapping else None,
        })

    return render(request, 'tests/execution_results.html', {
        'suite': suite,
        'execution': execution,
        'test_results': enhanced_results,
        'has_squash_token': bool(user.get('squash_token')),
    })


@login_required_json
@squash_token_required
@require_http_methods(["POST"])
def sync_to_squash(request, suite_id):
    """Sync execution results to Squash TM."""
    user = request.current_user
    suite = get_suite_or_404(suite_id, user['id'])

    if not suite:
        return JsonResponse({'error': 'Suite not found'}, status=404)

    # Get latest execution
    exec_repo = JsonExecutionRepository()
    executions = exec_repo.get_by_suite(suite_id, limit=1)

    if not executions:
        return JsonResponse({'error': 'No execution found to sync'}, status=400)

    execution = executions[0]
    test_results = execution.get('test_results', [])

    if not test_results:
        return JsonResponse({'error': 'No test results to sync'}, status=400)

    mapping_service = MappingService()

    sync_result = mapping_service.sync_to_squash(
        suite_id=suite_id,
        test_results=test_results,
        squash_url=user['squash_url'],
        squash_token=user['squash_token']
    )

    if sync_result['success']:
        # Mark execution as synced
        execution['squash_synced'] = True
        exec_repo.save(execution)

    return JsonResponse(sync_result)
