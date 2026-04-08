"""Views for accounts app."""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from core.decorators import login_required_json
from apps.accounts.forms import LoginForm, RegisterForm, ProfileForm, ChangePasswordForm
from apps.accounts.services.auth_service import AuthService


def login_view(request):
    """Handle user login."""
    if request.session.get('user_id'):
        return redirect('projects:project_list')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            auth_service = AuthService()
            user = auth_service.authenticate(
                form.cleaned_data['username'],
                form.cleaned_data['password']
            )

            if user:
                request.session['user_id'] = user['id']
                request.session['username'] = user['username']
                messages.success(request, f'Welcome back, {user["username"]}!')
                return redirect('projects:project_list')
            else:
                messages.error(request, 'Invalid username or password')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    """Handle user registration."""
    if request.session.get('user_id'):
        return redirect('projects:project_list')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            auth_service = AuthService()
            try:
                user = auth_service.register(
                    form.cleaned_data['username'],
                    form.cleaned_data['password']
                )
                request.session['user_id'] = user['id']
                request.session['username'] = user['username']
                messages.success(request, 'Account created successfully!')
                return redirect('accounts:profile')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


@require_http_methods(["POST"])
def logout_view(request):
    """Handle user logout."""
    request.session.flush()
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required_json
def profile_view(request):
    """View and update user profile."""
    auth_service = AuthService()
    user = request.current_user

    if not user:
        return redirect('accounts:login')

    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            auth_service.update_squash_credentials(
                user['id'],
                form.cleaned_data['squash_url'],
                form.cleaned_data['squash_token']
            )
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(initial={
            'squash_url': user.get('squash_url', ''),
            'squash_token': user.get('squash_token', ''),
        })

    return render(request, 'accounts/profile.html', {
        'form': form,
        'user': user,
    })


@login_required_json
def change_password_view(request):
    """Handle password change."""
    auth_service = AuthService()
    user = request.current_user

    if not user:
        return redirect('accounts:login')

    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            try:
                auth_service.update_password(
                    user['id'],
                    form.cleaned_data['current_password'],
                    form.cleaned_data['new_password']
                )
                messages.success(request, 'Password changed successfully!')
                return redirect('accounts:profile')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ChangePasswordForm()

    return render(request, 'accounts/change_password.html', {'form': form})


@login_required_json
@require_http_methods(["POST"])
def validate_squash_token_api(request):
    """API endpoint to validate Squash token."""
    from apps.squash.client import SquashClient

    user = request.current_user
    if not user or not user.get('squash_token') or not user.get('squash_url'):
        return JsonResponse({
            'valid': False,
            'message': 'Please configure your Squash credentials first.'
        })

    try:
        client = SquashClient(user['squash_url'], user['squash_token'])
        is_valid = client.validate_token()
        return JsonResponse({
            'valid': is_valid,
            'message': 'Token is valid!' if is_valid else 'Token is invalid or expired.'
        })
    except Exception as e:
        return JsonResponse({
            'valid': False,
            'message': f'Error validating token: {str(e)}'
        })
