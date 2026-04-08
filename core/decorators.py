"""Decorators for view functions."""
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages


def login_required_json(view_func):
    """
    Decorator that returns JSON error for unauthenticated AJAX requests,
    or redirects for regular requests.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Authentication required'}, status=401)
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def squash_token_required(view_func):
    """
    Decorator that checks if user has a valid Squash token.
    Returns JSON response with show_modal flag for AJAX requests.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, 'current_user', None)

        if not user or not user.get('squash_token'):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Squash token required',
                    'show_modal': True,
                    'message': 'Please configure your Squash API token in your profile.'
                }, status=401)
            messages.warning(request, 'Please configure your Squash API token to perform this action.')
            return redirect('accounts:profile')

        return view_func(request, *args, **kwargs)
    return wrapper
