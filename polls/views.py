from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .filters import CandidateFilter
from .models import Candidate, Nomination, Vote
from .serializers import (
    CandidateSerializer,
    NominationSerializer,
    VoteSerializer,
)


class NominationViewSet(ModelViewSet):
    queryset = Nomination.objects.all()
    serializer_class = NominationSerializer
    permission_classes = [IsAuthenticated]

    @action(methods=['GET'], detail=False)
    def active(self, request):
        nominations = Nomination.objects.filter(is_active=True)
        serializer = self.get_serializer(nominations, many=True)
        return Response(serializer.data)

    @action(methods=['POST'], detail=True)
    def stats(self, request, pk=None):
        nomination = self.get_object()
        data = (
            Vote.objects
            .filter(candidate__nomination=nomination)
            .values('candidate__name')
            .annotate(total=Count('id'))
        )
        return Response(data)

class CandidateViewSet(ModelViewSet):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
    ]
    filterset_class = CandidateFilter
    search_fields = ['name']

class VoteViewSet(ModelViewSet):
    serializer_class = VoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Vote.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
