from django.urls import path
from . import views

urlpatterns = [
    path('nominations/', views.NominationListView.as_view(), name='nomination_list'),
    path('nominations/add/', views.NominationCreateView.as_view(), name='nomination_add'),
    path('nominations/<int:pk>/edit/', views.NominationUpdateView.as_view(), name='nomination_edit'),
    path('nominations/<int:pk>/delete/', views.NominationDeleteView.as_view(), name='nomination_delete'),
]