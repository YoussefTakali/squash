"""URL patterns for test suite manager."""
from django.urls import path
from . import views

app_name = 'tests_manager'

urlpatterns = [
    path('', views.suite_list, name='suite_list'),
    path('create/', views.suite_create, name='suite_create'),
    path('<str:suite_id>/', views.suite_detail, name='suite_detail'),
    path('<str:suite_id>/edit/', views.suite_edit, name='suite_edit'),
    path('<str:suite_id>/delete/', views.suite_delete, name='suite_delete'),
    path('<str:suite_id>/scan/', views.suite_scan, name='suite_scan'),
    path('<str:suite_id>/execute/', views.suite_execute, name='suite_execute'),
    path('<str:suite_id>/mappings/', views.suite_mappings, name='suite_mappings'),
    path('<str:suite_id>/results/<str:execution_id>/', views.execution_results, name='execution_results'),
    path('api/<str:suite_id>/sync/', views.sync_to_squash, name='sync_to_squash'),
]
