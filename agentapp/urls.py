from django.contrib import admin
from django.urls import include, path

from django.conf import settings
from django.conf.urls.static import static

from support.api import api
from support.views import chat_page


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("", chat_page, name="chat"),
    path("", include("support.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
