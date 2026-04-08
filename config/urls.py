"""
URL configuration for squashed project.
"""
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/projects/', permanent=False), name='home'),
    path('accounts/', include('apps.accounts.urls')),
    path('squash/', include('apps.squash.urls')),
    path('projects/', include('apps.projects.urls')),
]
