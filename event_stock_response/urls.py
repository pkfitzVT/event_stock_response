# event_stock_response/urls.py
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/", include("django.contrib.auth.urls")
    ),  # login / logout / password-reset
    path("", include("catalog.urls")),  # hand everything else to the app
]
