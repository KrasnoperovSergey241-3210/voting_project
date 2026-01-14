from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from polls.views import (
    CandidateViewSet,
    NominationViewSet,
    VoteViewSet,
)

router = DefaultRouter()
router.register('nominations', NominationViewSet)
router.register('candidates', CandidateViewSet)
router.register('votes', VoteViewSet, basename='vote')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]
