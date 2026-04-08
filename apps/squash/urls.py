"""URL configuration for squash app."""
from django.urls import path
from . import views

app_name = "squash"

urlpatterns = [
    path("api/validate-token/", views.validate_token_api, name="validate_token"),
    path("api/projects/", views.get_projects_api, name="get_projects"),
    path("api/campaigns/<int:campaign_id>/", views.get_campaign_api, name="get_campaign"),
    path("api/iterations/<int:iteration_id>/tests/", views.get_iteration_tests_api, name="get_iteration_tests"),
]
