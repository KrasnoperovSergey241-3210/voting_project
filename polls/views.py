from django.db.models import Count, Q
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from rest_framework.pagination import PageNumberPagination

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .filters import CandidateFilter
from .models import Candidate, Nomination, Vote, JuryMember
from .serializers import (
    CandidateSerializer,
    NominationSerializer,
    VoteSerializer,
    JuryMemberSerializer,
)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50

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
    
    @action(methods=['GET'], detail=False)
    def stats_summary(self, request):
        """Пример ещё одного полезного action"""
        data = (
            Nomination.objects
            .filter(is_active=True)
            .annotate(
                candidate_count=Count('candidates'),
                total_votes=Count('candidates__votes')
            )
            .values('id', 'title', 'candidate_count', 'total_votes')
        )
        return Response(data)

class CandidateViewSet(ModelViewSet):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticated]

    pagination_class = StandardResultsSetPagination

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
            (Q(name__icontains="А") & ~Q(votes__user=user)) |
            Q(nomination__is_active=True)
        ).distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['GET'])
    def popular(self, request):
        qs = Candidate.objects.annotate(
            vote_count=Count('votes')
        ).order_by('-vote_count')[:10]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['GET'])
    def special_candidates(self, request):
        user = request.user
        queryset = Candidate.objects.filter(
            (Q(votes__user=user) & Q(nomination__is_active=True))
            |
            (~Q(votes__isnull=False) & ~Q(photo__isnull=True))
        ).select_related('nomination').distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['GET'])
    def controversial(self, request):
        user = request.user
        
        queryset = Candidate.objects.annotate(
            vote_count=Count('votes')
        ).filter(
            (Q(vote_count__gte=5) & Q(nomination__is_active=True)) |
            (Q(vote_count=0) & ~Q(photo__isnull=True) & ~Q(votes__user=user))
        ).select_related('nomination').distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def my_voted_and_popular(self, request):
        user = request.user
        
        my_voted = Q(votes__user=user)
        top_overall = Q(vote_count__gte=3)
        
        queryset = Candidate.objects.annotate(
            vote_count=Count('votes')
        ).filter(
            my_voted | top_overall
        ).order_by('-vote_count')[:10]

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class VoteViewSet(ModelViewSet):
    serializer_class = VoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Vote.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class JuryMemberViewSet(ModelViewSet):
    queryset = JuryMember.objects.all()
    serializer_class = JuryMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return JuryMember.objects.filter(
            Q(name__icontains='a') & Q(nominations__isnull=False)
        ).distinct()

    @action(detail=False, methods=['GET'])
    def with_active_nominations(self, request):
        queryset = JuryMember.objects.filter(
            nominations__is_active=True
        ).distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
class CandidateDetailView(DetailView):
    model = Candidate
    template_name = 'polls/candidate_detail.html'
    context_object_name = 'candidate'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_voted'] = Vote.objects.filter(
            user=self.request.user,
            candidate=self.object
        ).exists()
        context['vote_count'] = self.object.votes.count()
        return context

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