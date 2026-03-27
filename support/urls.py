from django.urls import path

from .views import chat_page, pdf_upload

urlpatterns = [
    path("", chat_page, name="chat-page"),
    path("upload-pdf/", pdf_upload, name="pdf-upload"),
]
