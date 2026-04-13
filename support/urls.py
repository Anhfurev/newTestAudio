from django.urls import path

from .views import (
    agent_dashboard,
    agent_login_page,
    apartment_page,
    chat_page,
    publish_apartment,
    submit_apartment_request,
)

urlpatterns = [
    path("", chat_page, name="chat-page"),
    path("apartments/", apartment_page, name="apartment-page"),
    path("apartments/submit/", submit_apartment_request, name="apartment-submit"),
    path("agent/login/", agent_login_page, name="agent-login"),
    path("agent/dashboard/", agent_dashboard, name="agent-dashboard"),
    path("agent/publish/<int:lead_id>/", publish_apartment, name="apartment-publish"),
]
