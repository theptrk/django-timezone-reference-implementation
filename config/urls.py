from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from timezones import views

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.inspector, name="inspector"),
    path("profile/", views.index, name="index"),
    path("examples/", RedirectView.as_view(pattern_name="index")),
    path("preferences/", views.preferences, name="preferences"),
    path("device-timezone/", views.device_timezone, name="device_timezone"),
    path("timezone-suggestion/", views.timezone_suggestion, name="timezone_suggestion"),
    path("events/", views.create_event, name="create_event"),
    path("api/events/", views.events_api, name="events_api"),
]
