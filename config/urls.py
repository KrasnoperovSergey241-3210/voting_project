from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from polls import views

urlpatterns = [
    path("test-500/", views.test_500_view, name="test-500"),  # Добавьте САМЫМ ПЕРВЫМ
    path("admin/", admin.site.urls),
    path("silk/", include("silk.urls", namespace="silk")),
    path("", include("polls.urls")),
    path("", include("django.contrib.auth.urls")),
    path("register/", views.register, name="register"),
    path("auth/", include("social_django.urls", namespace="social")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
