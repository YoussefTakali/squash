"""Views for squash app."""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from core.decorators import login_required_json, squash_token_required
from apps.squash.services.squash_service import SquashService


@login_required_json
@require_http_methods(["POST"])
def validate_token_api(request):
    """Validate Squash token."""
    user = request.current_user
    service = SquashService.from_user(user)
    
    if not service:
        return JsonResponse({
            "valid": False,
            "message": "Please configure your Squash credentials first."
        })
    
    try:
        is_valid = service.validate_credentials()
        return JsonResponse({
            "valid": is_valid,
            "message": "Token is valid!" if is_valid else "Token is invalid or expired."
        })
    except Exception as e:
        return JsonResponse({
            "valid": False,
            "message": f"Error validating token: {str(e)}"
        })


@login_required_json
@squash_token_required
@require_http_methods(["GET"])
def get_projects_api(request):
    """Get Squash projects."""
    user = request.current_user
    service = SquashService.from_user(user)
    
    try:
        projects = service.get_projects_list()
        return JsonResponse({"projects": projects})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required_json
@squash_token_required
@require_http_methods(["GET"])
def get_campaign_api(request, campaign_id: int):
    """Get campaign with iterations."""
    user = request.current_user
    service = SquashService.from_user(user)
    
    try:
        campaign = service.get_campaign_structure(campaign_id)
        return JsonResponse({"campaign": campaign})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required_json
@squash_token_required
@require_http_methods(["GET"])
def get_iteration_tests_api(request, iteration_id: int):
    """Get iteration test plan items."""
    user = request.current_user
    service = SquashService.from_user(user)
    
    try:
        tests = service.get_iteration_tests(iteration_id)
        return JsonResponse({"tests": tests})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
