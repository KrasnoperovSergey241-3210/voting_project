from datetime import timedelta
from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .filters import CandidateFilter
from .models import Candidate, FavoriteCandidate, JuryMember, Nomination, Vote
from .serializers import (
    CandidateSerializer,
    JuryMemberSerializer,
    NominationSerializer,
    VoteSerializer,
)
from .tasks import send_welcome_email


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50


class NominationViewSet(ModelViewSet):
    queryset = Nomination.objects.all()
    serializer_class = NominationSerializer
    permission_classes = [IsAuthenticated]

    @action(methods=["GET"], detail=False)
    def active(self, request: Request) -> Response:
        nominations = Nomination.objects.filter(is_active=True)
        serializer = self.get_serializer(nominations, many=True)
        return Response(serializer.data)

    @action(methods=["POST"], detail=True)
    def stats(self, request: Request, pk: Optional[int] = None) -> Response:
        nomination = self.get_object()
        data = (
            Vote.objects.filter(candidate__nomination=nomination)
            .values("candidate__name")
            .annotate(total=Count("id"))
        )
        return Response(data)

    @action(methods=["GET"], detail=False)
    def stats_summary(self, request: Request) -> Response:
        data = (
            Nomination.objects.filter(is_active=True)
            .annotate(
                candidate_count=Count("candidates"),
                total_votes=Count("candidates__votes"),
            )
            .values("id", "title", "candidate_count", "total_votes")
        )
        return Response(data)

    @action(detail=False, methods=["get"])
    def recently_active_with_votes(self, request: Request) -> Response:
        thirty_days_ago = timezone.now() - timedelta(days=30)

        queryset = (
            self.get_queryset()
            .annotate(vote_count=Count("candidates__votes", distinct=True))
            .filter(
                Q(created_at__gte=thirty_days_ago) & Q(is_active=True)
                | Q(vote_count__gte=5)
            )
            .filter(~Q(is_active=False))
            .distinct()
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def high_activity_or_old_active(self, request: Request) -> Response:
        ninety_days_ago = timezone.now() - timedelta(days=90)

        queryset = (
            self.get_queryset()
            .annotate(candidate_count=Count("candidates"))
            .filter(
                (Q(candidate_count__gt=10) & Q(is_active=True))
                | Q(created_at__lte=ninety_days_ago)
            )
            .filter(~Q(is_active=False))
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def controversial_or_trending(self, request: Request) -> Response:
        seven_days_ago = timezone.now() - timedelta(days=7)

        queryset = (
            self.get_queryset()
            .annotate(
                total_votes=Count("candidates__votes", distinct=True),
                recent_votes=Count(
                    "candidates__votes",
                    filter=Q(candidates__votes__created_at__gte=seven_days_ago),
                    distinct=True,
                ),
            )
            .filter((Q(total_votes__lt=3) & Q(is_active=True)) | Q(recent_votes__gt=5))
            .filter(~Q(is_active=False))
            .distinct()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def jury_active_or_no_jury(self, request: Request) -> Response:
        queryset = (
            self.get_queryset()
            .filter(is_active=True)
            .annotate(
                jury_count=Count("jury_members", distinct=True),
                vote_count=Count("candidates__votes", distinct=True),
            )
            .filter(Q(jury_count__gt=0) | (Q(jury_count=0) & Q(vote_count__gt=8)))
            .distinct()
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CandidateViewSet(ModelViewSet):
    queryset = Candidate.objects.all().order_by("id")
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticated]

    pagination_class = StandardResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
    ]
    filterset_class = CandidateFilter
    search_fields = ["name"]

    def get_queryset(self) -> QuerySet[Candidate]:
        user = self.request.user
        qs = (
            super()
            .get_queryset()
            .select_related("nomination")
            .annotate(
                vote_count=Count("votes", distinct=True),
                favorites_count=Count("favoritecandidate", distinct=True),
            )
        )
        qs = qs.filter(votes__user=user)

        nomination_id = self.request.GET.get("nomination_id")
        if nomination_id:
            qs = qs.filter(nomination_id=nomination_id)

        return qs.distinct()

    def get_serializer_context(self) -> Dict[str, Any]:
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            favorites = FavoriteCandidate.objects.filter(
                user=self.request.user
            ).values_list("candidate_id", flat=True)
            context["favorites"] = list(favorites)
        else:
            context["favorites"] = []
        return context

    @action(detail=False, methods=["GET"])
    def complex_filter(self, request: Request) -> Response:
        user = request.user
        queryset = Candidate.objects.filter(
            (Q(name__icontains="a") & ~Q(votes__user=user))
            | Q(nomination__is_active=True)
        ).distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def popular(self, request: Request) -> Response:
        qs = Candidate.objects.annotate(vote_count=Count("votes")).order_by(
            "-vote_count"
        )[:10]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def special_candidates(self, request: Request) -> Response:
        user = request.user
        queryset = (
            Candidate.objects.filter(
                (Q(votes__user=user) & Q(nomination__is_active=True))
                | (~Q(votes__isnull=False) & ~Q(photo__isnull=True))
            )
            .select_related("nomination")
            .distinct()
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def controversial(self, request: Request) -> Response:
        user = request.user

        queryset = (
            Candidate.objects.annotate(vote_count=Count("votes"))
            .filter(
                (Q(vote_count__gte=5) & Q(nomination__is_active=True))
                | (Q(vote_count=0) & ~Q(photo__isnull=True) & ~Q(votes__user=user))
            )
            .select_related("nomination")
            .distinct()
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def my_voted_and_popular(self, request: Request) -> Response:
        user = request.user

        my_voted = Q(votes__user=user)
        top_overall = Q(vote_count__gte=3)

        queryset = (
            Candidate.objects.annotate(vote_count=Count("votes"))
            .filter(my_voted | top_overall)
            .order_by("-vote_count")[:10]
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class VoteViewSet(ModelViewSet):
    serializer_class = VoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Vote]:
        return Vote.objects.filter(user=self.request.user).select_related(
            "candidate", "candidate__nomination"
        )

    def perform_create(self, serializer: VoteSerializer) -> None:
        serializer.save(user=self.request.user)


class JuryMemberViewSet(ModelViewSet):
    queryset = JuryMember.objects.all()
    serializer_class = JuryMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[JuryMember]:
        return JuryMember.objects.filter(Q(nominations__isnull=False)).distinct()

    @action(detail=False, methods=["GET"])
    def with_active_nominations(self, request: Request) -> Response:
        queryset = JuryMember.objects.filter(nominations__is_active=True).distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CandidateDetailView(LoginRequiredMixin, DetailView):
    model = Candidate
    template_name = "polls/candidate_detail.html"
    context_object_name = "candidate"
    login_url = "/login/"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["user_voted"] = Vote.objects.filter(
            user=self.request.user, candidate=self.object
        ).exists()
        context["vote_count"] = self.object.votes.count()
        return context


class NominationListView(LoginRequiredMixin, ListView):
    model = Nomination
    template_name = "polls/nomination_list.html"
    context_object_name = "nominations"
    paginate_by = 5
    login_url = "/login/"


class NominationCreateView(LoginRequiredMixin, CreateView):
    model = Nomination
    fields = ["title", "is_active"]
    template_name = "polls/nomination_form.html"
    success_url = reverse_lazy("nomination_list")


class NominationUpdateView(LoginRequiredMixin, UpdateView):
    model = Nomination
    fields = ["title", "is_active"]
    template_name = "polls/nomination_form.html"
    success_url = reverse_lazy("nomination_list")


class NominationDeleteView(LoginRequiredMixin, DeleteView):
    model = Nomination
    template_name = "polls/nomination_confirm_delete.html"
    success_url = reverse_lazy("nomination_list")


class CandidatesByNominationView(LoginRequiredMixin, ListView):
    model = Candidate
    template_name = "polls/candidates_by_nomination.html"
    context_object_name = "candidates"
    paginate_by = 5

    def get_queryset(self) -> QuerySet[Candidate]:
        nomination_id = self.kwargs.get("nomination_id")
        return Candidate.objects.filter(nomination_id=nomination_id).select_related(
            "nomination"
        )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["nomination"] = Nomination.objects.get(pk=self.kwargs["nomination_id"])
        return context


@login_required
def vote_for_candidate(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method == "POST":
        candidate = get_object_or_404(Candidate, pk=pk)

        if not candidate.nomination.is_active:
            messages.error(request, "Голосование в этой номинации закрыто!")
        elif Vote.objects.filter(
            user=request.user, candidate__nomination=candidate.nomination
        ).exists():
            messages.error(request, "Вы уже голосовали в этой номинации!")
        else:
            Vote.objects.create(user=request.user, candidate=candidate)
            messages.success(request, f"Голос за {candidate.name} учтён!")

        return redirect("candidate_detail", pk=pk)

    return redirect("candidate_detail", pk=pk)


def register(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Регистрация успешна! Добро пожаловать!")
            send_welcome_email.delay(user.id)
            return redirect("nomination_list")
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {"form": form})


def test_500_view(request):
    1 / 0
