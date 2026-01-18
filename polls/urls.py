from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('api/nominations', views.NominationViewSet, basename='nomination')
router.register('api/candidates', views.CandidateViewSet, basename='candidate')
router.register('api/votes', views.VoteViewSet, basename='vote')
router.register('api/jury-members', views.JuryMemberViewSet, basename='jury-member')

urlpatterns = [
    path('nominations/', views.NominationListView.as_view(), name='nomination_list'),
    path('nominations/add/', views.NominationCreateView.as_view(), name='nomination_add'),
    path('nominations/<int:pk>/edit/', views.NominationUpdateView.as_view(), name='nomination_edit'),
    path('nominations/<int:pk>/delete/', views.NominationDeleteView.as_view(), name='nomination_delete'),

    path('candidates/<int:pk>/', views.CandidateDetailView.as_view(), name='candidate_detail'),
    path('candidates/<slug:slug>/', views.CandidateDetailView.as_view(), name='candidate_detail_slug'),

    path('', include(router.urls)),
]
