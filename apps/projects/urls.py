"""URL configuration for projects app."""
from django.urls import path
from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("connect/", views.project_connect, name="project_connect"),
    path("browse-folder/", views.browse_folder, name="browse_folder"),
    path("squash-projects/", views.squash_projects, name="squash_projects"),
    path("<str:project_id>/", views.project_detail, name="project_detail"),
    path("<str:project_id>/scan/", views.project_scan, name="project_scan"),
    path("<str:project_id>/mappings/", views.project_mappings, name="project_mappings"),
    path("<str:project_id>/autolink/preview/", views.autolink_preview, name="autolink_preview"),
    path("<str:project_id>/autolink/apply/", views.autolink_apply, name="autolink_apply"),
    path("<str:project_id>/select-scopes/", views.project_select_scopes, name="project_select_scopes"),
    path("<str:project_id>/execute/", views.project_execute, name="project_execute"),
    path("<str:project_id>/install-listener/", views.project_install_listener, name="project_install_listener"),
    path("<str:project_id>/delete/", views.project_delete, name="project_delete"),
]
