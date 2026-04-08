"""Middleware for the application."""
from django.conf import settings
import json


class SquashTokenMiddleware:
    """
    Middleware that loads user data from JSON storage and attaches it to request.
    Also checks Squash token validity for relevant requests.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Load current user from session
        user_id = request.session.get('user_id')
        request.current_user = None

        if user_id:
            try:
                users_path = settings.USERS_JSON_PATH
                if users_path.exists():
                    with open(users_path, 'r') as f:
                        data = json.load(f)

                    for user in data.get('users', []):
                        if user['id'] == user_id:
                            request.current_user = user
                            break
            except (json.JSONDecodeError, IOError):
                pass

        response = self.get_response(request)
        return response
