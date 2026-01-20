from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from polls.views import (
    CandidateViewSet,
    JuryMemberViewSet,
    NominationViewSet,
    VoteViewSet,
    register,
)

router = DefaultRouter()
router.register("nominations", NominationViewSet)
router.register("candidates", CandidateViewSet)
router.register("votes", VoteViewSet, basename="vote")
router.register("jury-members", JuryMemberViewSet, basename="jury-member")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("", include("polls.urls")),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="nomination_list"),
        name="logout",
    ),
    path("register/", register, name="register"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
