from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.db.models import Q
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

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

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(votes__user=self.request.user)
        nomination_id = self.request.GET.get('nomination_id')
        if nomination_id:
            qs = qs.filter(nomination_id=nomination_id)
        return qs.distinct()

    @action(detail=False, methods=['GET'])
    def complex_filter(self, request):
        user = request.user
        queryset = Candidate.objects.filter(
            Q(name__icontains="А") & ~Q(votes__user=user) | Q(nomination__is_active=True)
        ).distinct()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class VoteViewSet(ModelViewSet):
    serializer_class = VoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Vote.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class NominationListView(ListView):
    model = Nomination
    template_name = 'polls/nomination_list.html'
    context_object_name = 'nominations'
    paginate_by = 5

class NominationCreateView(CreateView):
    model = Nomination
    fields = ['title', 'is_active']
    template_name = 'polls/nomination_form.html'
    success_url = reverse_lazy('nomination_list')

class NominationUpdateView(UpdateView):
    model = Nomination
    fields = ['title', 'is_active']
    template_name = 'polls/nomination_form.html'
    success_url = reverse_lazy('nomination_list')

class NominationDeleteView(DeleteView):
    model = Nomination
    template_name = 'polls/nomination_confirm_delete.html'
    success_url = reverse_lazy('nomination_list')
