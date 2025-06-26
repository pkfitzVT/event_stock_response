# catalog/urls.py
from django.urls import path

from . import views

app_name = "catalog"  # enables namespacing:  catalog:chat_flow  etc.

urlpatterns = [
    path("", views.home, name="home"),  # /
    path("chat/", views.chat_flow, name="chat_flow"),  # /chat/
    path("analysis/", views.analysis_list, name="analysis_list"),
    path("analysis/<int:pk>/", views.analysis_detail, name="analysis_detail"),
    path("analysis/<int:pk>/vote/<str:action>/", views.vote, name="vote"),
]
