"""Views for projects app."""
import json
import threading
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods

from core.decorators import login_required_json, squash_token_required
from apps.projects.services.project_service import ProjectService
from apps.projects.services.execution_service import ExecutionService


def _open_folder_dialog():
    """Open native folder dialog and return selected path."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.attributes('-topmost', True)  # Bring dialog to front

    folder_path = filedialog.askdirectory(
        title="Select Robot Framework Project Folder"
    )

    root.destroy()
    return folder_path


@require_http_methods(["POST"])
def browse_folder(request):
    """Open Windows folder picker dialog and return selected path."""
    result = {"path": ""}

    def run_dialog():
        result["path"] = _open_folder_dialog()

    # Run dialog in main thread (tkinter requirement)
    thread = threading.Thread(target=run_dialog)
    thread.start()
    thread.join(timeout=60)  # Wait up to 60 seconds

    return JsonResponse({"path": result["path"]})


@login_required_json
def project_list(request):
    user = request.current_user
    service = ProjectService()
    projects = service.get_user_projects(user["id"])
    return render(request, "projects/list.html", {"projects": projects})


@login_required_json
def project_connect(request):
    user = request.current_user
    
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        directory_path = request.POST.get("directory_path", "").strip()
        
        if not name:
            messages.error(request, "Project name is required.")
            return render(request, "projects/connect.html")
        
        if not directory_path:
            messages.error(request, "Directory path is required.")
            return render(request, "projects/connect.html")
        
        service = ProjectService()
        try:
            project = service.create_project(user["id"], name, directory_path)
            total = sum(len(s["test_cases"]) for s in project["test_suites"])
            messages.success(request, f"Project created! Found {total} test cases.")
            return redirect("projects:project_detail", project_id=project["id"])
        except ValueError as e:
            messages.error(request, str(e))
    
    return render(request, "projects/connect.html")


@login_required_json
def project_detail(request, project_id: str):
    user = request.current_user
    service = ProjectService()
    project = service.get_project(project_id)
    
    if not project or project["user_id"] != user["id"]:
        messages.error(request, "Project not found.")
        return redirect("projects:project_list")
    
    total_tests = sum(len(s["test_cases"]) for s in project.get("test_suites", []))
    mapped_tests = sum(
        1 for s in project.get("test_suites", [])
        for tc in s.get("test_cases", [])
        if tc.get("squash_test_case_id")
    )
    
    return render(request, "projects/detail.html", {
        "project": project,
        "total_tests": total_tests,
        "mapped_tests": mapped_tests,
    })


@login_required_json
@require_http_methods(["POST"])
def project_scan(request, project_id: str):
    user = request.current_user
    service = ProjectService()
    project = service.get_project(project_id)
    
    if not project or project["user_id"] != user["id"]:
        return JsonResponse({"error": "Project not found"}, status=404)
    
    try:
        service.rescan_project(project_id)
        messages.success(request, "Project rescanned successfully!")
        return JsonResponse({"success": True})
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required_json
def project_mappings(request, project_id: str):
    user = request.current_user
    service = ProjectService()
    project = service.get_project(project_id)
    
    if not project or project["user_id"] != user["id"]:
        messages.error(request, "Project not found.")
        return redirect("projects:project_list")
    
    if request.method == "POST":
        mappings = {}
        for key, value in request.POST.items():
            if key.startswith("mapping_") and value:
                test_name = key[8:]
                try:
                    mappings[test_name] = int(value)
                except ValueError:
                    pass
        
        campaign_id = request.POST.get("squash_campaign_id")
        iteration_id = request.POST.get("squash_iteration_id")
        
        if campaign_id:
            try:
                service.update_squash_config(project_id, campaign_id=int(campaign_id))
            except ValueError:
                pass
        
        if iteration_id:
            try:
                service.update_squash_config(project_id, iteration_id=int(iteration_id))
            except ValueError:
                pass
        
        if mappings:
            service.update_all_mappings(project_id, mappings)
        
        messages.success(request, "Mappings saved successfully!")
        return redirect("projects:project_mappings", project_id=project_id)
    
    test_cases = service.get_all_test_cases(project_id)
    return render(request, "projects/mappings.html", {
        "project": project,
        "test_cases": test_cases,
    })


@login_required_json
def project_select_scopes(request, project_id: str):
    user = request.current_user
    service = ProjectService()
    project = service.get_project(project_id)
    
    if not project or project["user_id"] != user["id"]:
        messages.error(request, "Project not found.")
        return redirect("projects:project_list")
    
    return render(request, "projects/select_scopes.html", {"project": project})


@login_required_json
@require_http_methods(["POST"])
def project_delete(request, project_id: str):
    user = request.current_user
    service = ProjectService()
    project = service.get_project(project_id)
    
    if not project or project["user_id"] != user["id"]:
        return JsonResponse({"error": "Project not found"}, status=404)
    
    service.delete_project(project_id)
    messages.success(request, "Project deleted successfully!")
    return JsonResponse({"success": True, "redirect": "/projects/"})


@login_required_json
@squash_token_required
@require_http_methods(["POST"])
def project_execute(request, project_id: str):
    """Execute tests for a project."""
    user = request.current_user
    project_service = ProjectService()
    project = project_service.get_project(project_id)

    if not project or project["user_id"] != user["id"]:
        return JsonResponse({"error": "Project not found"}, status=404)

    # Get selected test files from request
    try:
        data = json.loads(request.body) if request.body else {}
        test_files = data.get("test_files", [])
    except json.JSONDecodeError:
        test_files = []

    execution_service = ExecutionService()

    try:
        # Prepare execution (deploy listener, generate config)
        prep = execution_service.prepare_execution(project_id, user, test_files or None)

        # Execute tests
        result = execution_service.execute_tests(project_id, user, test_files or None)

        return JsonResponse({
            "success": result.success,
            "return_code": result.return_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration": result.duration,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "mappings_synced": prep["mappings_count"]
        })

    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Execution failed: {str(e)}"}, status=500)


@login_required_json
@squash_token_required
@require_http_methods(["POST"])
def project_install_listener(request, project_id: str):
    """Install listener to project directory."""
    user = request.current_user
    project_service = ProjectService()
    project = project_service.get_project(project_id)

    if not project or project["user_id"] != user["id"]:
        return JsonResponse({"error": "Project not found"}, status=404)

    from apps.projects.services.listener_service import ListenerService

    try:
        listener_service = ListenerService()
        mappings = project_service.get_mappings_dict(project_id)

        if not mappings:
            return JsonResponse({"error": "No test mappings configured"}, status=400)

        if not project.get("squash_iteration_id"):
            return JsonResponse({"error": "Squash iteration ID not configured"}, status=400)

        paths = listener_service.create_listener_package(
            project_directory=project["directory_path"],
            squash_url=user.get("squash_url"),
            token=user.get("squash_token"),
            iteration_id=project["squash_iteration_id"],
            mappings=mappings
        )

        # Update project to mark listener as installed
        project["listener_installed"] = True
        project_service.repo.save(project)

        # Get the robot command
        command = listener_service.get_robot_command(project["directory_path"])

        return JsonResponse({
            "success": True,
            "listener_path": str(paths["listener"]),
            "config_path": str(paths["config"]),
            "command": command,
            "message": "Listener installed successfully!"
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required_json
@squash_token_required
def autolink_preview(request, project_id: str):
    """Preview auto-link matches without applying them."""
    user = request.current_user
    project_service = ProjectService()
    project = project_service.get_project(project_id)

    if not project or project["user_id"] != user["id"]:
        return JsonResponse({"error": "Project not found"}, status=404)

    from apps.projects.services.autolink_service import AutoLinkService

    try:
        service = AutoLinkService.from_user(user)
        if not service:
            return JsonResponse({"error": "Squash credentials not configured"}, status=400)

        # Get threshold from query params (default 0.6)
        threshold = float(request.GET.get("threshold", 0.6))

        # Get all robot test cases
        robot_test_cases = project_service.get_all_test_cases(project_id)

        # Get project name to match with campaign folder
        project_name = project.get("name", "")

        # Find matches using campaign folder matching by project name
        result = service.auto_link_by_project_name(
            project_name=project_name,
            robot_test_cases=robot_test_cases,
            threshold=threshold,
            skip_already_mapped=False  # Show all for preview
        )

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required_json
@squash_token_required
@require_http_methods(["POST"])
def autolink_apply(request, project_id: str):
    """Apply auto-link matches to project."""
    user = request.current_user
    project_service = ProjectService()
    project = project_service.get_project(project_id)

    if not project or project["user_id"] != user["id"]:
        return JsonResponse({"error": "Project not found"}, status=404)

    from apps.projects.services.autolink_service import AutoLinkService

    try:
        data = json.loads(request.body) if request.body else {}
        selected_matches = data.get("matches", [])

        if not selected_matches:
            return JsonResponse({"error": "No matches provided"}, status=400)

        # Build mappings dict from selected matches
        mappings = {}
        for match in selected_matches:
            robot_name = match.get("robot_test_name")
            squash_id = match.get("squash_test_case_id")
            if robot_name and squash_id:
                mappings[robot_name] = int(squash_id)

        # Apply mappings
        project_service.update_all_mappings(project_id, mappings)

        return JsonResponse({
            "success": True,
            "applied_count": len(mappings),
            "message": f"Successfully linked {len(mappings)} test cases"
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required_json
@squash_token_required
def squash_projects(request):
    """Get list of Squash projects for selection."""
    user = request.current_user

    from apps.projects.services.autolink_service import AutoLinkService

    try:
        service = AutoLinkService.from_user(user)
        if not service:
            return JsonResponse({"error": "Squash credentials not configured"}, status=400)

        projects = service.fetch_squash_projects()
        return JsonResponse({"projects": projects})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
