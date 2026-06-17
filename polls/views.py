"""
View-функции и классы-представления для приложения polls.
"""

from datetime import timedelta
from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
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
from .permissions import IsAdminOrReadOnly, IsAdminUser, IsOwnerOrAdmin
from .serializers import (
    CandidateSerializer,
    JuryMemberSerializer,
    NominationSerializer,
    VoteSerializer,
)
from .tasks import send_welcome_email


class AdminRequiredMixin(UserPassesTestMixin):
    """
    Миксин для проверки прав администратора во всех запросах (GET и POST).
    """

    raise_exception = True

    def test_func(self) -> bool:
        """
        Проверяет, является ли пользователь администратором.

        Returns:
            bool: True если пользователь администратор, иначе False.
        """
        return self.request.user.is_authenticated and self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        """
        Переопределяет dispatch для проверки прав при любом типе запроса.

        Args:
            request: HTTP запрос.
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.

        Returns:
            HttpResponse: Ответ от представления или PermissionDenied.

        Raises:
            PermissionDenied: Если пользователь не является администратором.
        """
        if not self.test_func():
            raise PermissionDenied("У вас нет прав для этого действия.")
        return super().dispatch(request, *args, **kwargs)


class StandardResultsSetPagination(PageNumberPagination):
    """
    Кастомная пагинация для API.

    Attributes:
        page_size (int): Количество элементов на странице по умолчанию.
        page_size_query_param (str): GET-параметр для изменения размера страницы.
        max_page_size (int): Максимальный размер страницы.
    """

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50


class NominationViewSet(ModelViewSet):
    """
    ViewSet для управления номинациями.

    Права доступа:
        - Чтение (GET): все авторизованные пользователи
        - Создание, редактирование, удаление: только администраторы

    Attributes:
        queryset (QuerySet): Все номинации.
        serializer_class (Serializer): Сериализатор для номинаций.
        permission_classes (list): Права доступа.
    """

    queryset = Nomination.objects.all()
    serializer_class = NominationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    @action(methods=["GET"], detail=False)
    def active(self, request: Request) -> Response:
        """
        Возвращает список активных номинаций.

        Args:
            request: HTTP запрос.

        Returns:
            Response: Сериализованный список активных номинаций.
        """
        nominations = Nomination.objects.filter(is_active=True)
        serializer = self.get_serializer(nominations, many=True)
        return Response(serializer.data)

    @action(methods=["POST"], detail=True)
    def stats(self, request: Request, pk: Optional[int] = None) -> Response:
        """
        Возвращает статистику голосов по кандидатам в конкретной номинации.

        Args:
            request: HTTP запрос.
            pk: Идентификатор номинации.

        Returns:
            Response: Список кандидатов с количеством голосов.
        """
        nomination = self.get_object()
        data = (
            Vote.objects.filter(candidate__nomination=nomination)
            .values("candidate__name")
            .annotate(total=Count("id"))
        )
        return Response(data)

    @action(methods=["GET"], detail=False)
    def stats_summary(self, request: Request) -> Response:
        """
        Возвращает сводку по всем активным номинациям.

        Args:
            request: HTTP запрос.

        Returns:
            Response: Данные о количестве кандидатов и голосов по номинациям.
        """
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
        """
        Возвращает номинации, созданные за последние 30 дней ИЛИ с >= 5 голосами.

        Args:
            request: HTTP запрос.

        Returns:
            Response: Отфильтрованный список номинаций.
        """
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
        """
        Возвращает номинации с > 10 кандидатами ИЛИ созданные более 90 дней назад.

        Args:
            request: HTTP запрос.

        Returns:
            Response: Отфильтрованный список номинаций.
        """
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
        """
        Возвращает номинации с < 3 голосами ИЛИ > 5 голосов за последние 7 дней.

        Args:
            request: HTTP запрос.

        Returns:
            Response: Отфильтрованный список номинаций.
        """
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
        """
        Возвращает активные номинации с жюри ИЛИ без жюри, но с > 8 голосами.

        Args:
            request: HTTP запрос.

        Returns:
            Response: Отфильтрованный список номинаций.
        """
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
    """
    ViewSet для управления кандидатами.

    Права доступа:
        - Чтение (GET): все авторизованные пользователи
        - Создание, редактирование, удаление: только администраторы

    Attributes:
        queryset (QuerySet): Все кандидаты.
        serializer_class (Serializer): Сериализатор для кандидатов.
        permission_classes (list): Права доступа.
        pagination_class (Pagination): Класс пагинации.
        filter_backends (list): Бэкенды фильтрации.
        filterset_class (FilterSet): Класс фильтров.
        search_fields (list): Поля для поиска.
    """

    queryset = Candidate.objects.all().order_by("id")
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    pagination_class = StandardResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
    ]
    filterset_class = CandidateFilter
    search_fields = ["name"]

    def get_queryset(self) -> QuerySet[Candidate]:
        """
        Возвращает queryset кандидатов с аннотациями и фильтрацией.

        Returns:
            QuerySet[Candidate]: Отфильтрованный queryset с аннотациями:
                - vote_count: количество голосов
                - favorites_count: количество добавлений в избранное
        """
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
        """
        Добавляет список избранных кандидатов в контекст сериализатора.

        Returns:
            Dict[str, Any]: Контекст с полем 'favorites'.
        """
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
        """
        Сложная фильтрация кандидатов с использованием Q.

        Условия:
            - имя содержит 'a' И пользователь не голосовал
            ИЛИ номинация активна

        Args:
            request: HTTP запрос.

        Returns:
            Response: Отфильтрованный список кандидатов.
        """
        user = request.user
        queryset = Candidate.objects.filter(
            (Q(name__icontains="a") & ~Q(votes__user=user))
            | Q(nomination__is_active=True)
        ).distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def popular(self, request: Request) -> Response:
        """
        Возвращает топ-10 самых популярных кандидатов.

        Args:
            request: HTTP запрос.

        Returns:
            Response: Сериализованные данные кандидатов,
                     отсортированные по убыванию голосов.
        """
        qs = Candidate.objects.annotate(vote_count=Count("votes")).order_by(
            "-vote_count"
        )[:10]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def special_candidates(self, request: Request) -> Response:
        """
        Специальная выборка кандидатов.

        Условия:
            - пользователь голосовал И номинация активна
            ИЛИ есть голоса И есть фото

        Args:
            request: HTTP запрос.

        Returns:
            Response: Отфильтрованный список кандидатов.
        """
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
        """
        Возвращает "спорных" кандидатов.

        Условия:
            - >= 5 голосов И номинация активна
            ИЛИ 0 голосов И есть фото И пользователь не голосовал

        Args:
            request: HTTP запрос.

        Returns:
            Response: Отфильтрованный список кандидатов.
        """
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
        """
        Возвращает кандидатов, за которых голосовал пользователь, ИЛИ популярных.

        Условия:
            - пользователь голосовал
            ИЛИ >= 3 голосов

        Args:
            request: HTTP запрос.

        Returns:
            Response: Топ-10 кандидатов.
        """
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
    """
    ViewSet для управления голосами пользователя.

    Права доступа:
        - Пользователь может управлять только своими голосами
        - Администратор может управлять любыми голосами

    Attributes:
        serializer_class (Serializer): Сериализатор для голосов.
        permission_classes (list): Права доступа.
    """

    serializer_class = VoteSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self) -> QuerySet[Vote]:
        """
        Возвращает голоса с учетом прав доступа.

        Returns:
            QuerySet[Vote]:
                - Для администратора: все голоса
                - Для обычного пользователя: только его голоса
        """
        if self.request.user.is_staff:
            return Vote.objects.all().select_related(
                "candidate", "candidate__nomination"
            )
        return Vote.objects.filter(user=self.request.user).select_related(
            "candidate", "candidate__nomination"
        )

    def perform_create(self, serializer: VoteSerializer) -> None:
        """
        Сохраняет голос с привязкой к текущему пользователю.

        Args:
            serializer: Сериализатор с данными голоса.
        """
        serializer.save(user=self.request.user)


class JuryMemberViewSet(ModelViewSet):
    """
    ViewSet для управления членами жюри.

    Права доступа:
        - Только для администраторов (полный доступ)

    Attributes:
        queryset (QuerySet): Члены жюри с номинациями.
        serializer_class (Serializer): Сериализатор для членов жюри.
        permission_classes (list): Права доступа.
    """

    queryset = JuryMember.objects.all()
    serializer_class = JuryMemberSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self) -> QuerySet[JuryMember]:
        """
        Возвращает членов жюри, у которых есть номинации.

        Returns:
            QuerySet[JuryMember]: Отфильтрованный queryset.
        """
        return JuryMember.objects.filter(Q(nominations__isnull=False)).distinct()

    @action(detail=False, methods=["GET"])
    def with_active_nominations(self, request: Request) -> Response:
        """
        Возвращает членов жюри, участвующих в активных номинациях.

        Args:
            request: HTTP запрос.

        Returns:
            Response: Сериализованный список членов жюри.
        """
        queryset = JuryMember.objects.filter(nominations__is_active=True).distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CandidateDetailView(LoginRequiredMixin, DetailView):
    """
    Представление для просмотра детальной информации о кандидате.

    Права доступа:
        - Только для авторизованных пользователей

    Attributes:
        model (Model): Модель Candidate.
        template_name (str): Путь к шаблону.
        context_object_name (str): Имя объекта в контексте.
        login_url (str): URL для перенаправления при отсутствии авторизации.
    """

    model = Candidate
    template_name = "polls/candidate_detail.html"
    context_object_name = "candidate"
    login_url = "/login/"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Добавляет в контекст информацию о голосовании пользователя.

        Args:
            **kwargs: Дополнительные аргументы.

        Returns:
            Dict[str, Any]: Контекст с полями:
                - user_voted_for_this_candidate: голосовал ли юзер за этого кандидата
                - user_voted_in_nomination: голосовал ли пользователь в этой номинации
                - user_voted_candidate_name: имя кандидата,за которого проголосовал юзер
                - vote_count: общее количество голосов за кандидата
        """
        context = super().get_context_data(**kwargs)
        user_vote = Vote.objects.filter(
            user=self.request.user, candidate__nomination=self.object.nomination
        ).first()

        context["user_voted_for_this_candidate"] = Vote.objects.filter(
            user=self.request.user, candidate=self.object
        ).exists()
        context["user_voted_in_nomination"] = user_vote is not None
        context["user_voted_candidate_name"] = (
            user_vote.candidate.name if user_vote else None
        )
        context["vote_count"] = self.object.votes.count()
        return context


class NominationListView(LoginRequiredMixin, ListView):
    """
    Представление для отображения списка номинаций с пагинацией.

    Права доступа:
        - Только для авторизованных пользователей

    Attributes:
        model (Model): Модель Nomination.
        template_name (str): Путь к шаблону.
        context_object_name (str): Имя объекта в контексте.
        paginate_by (int): Количество элементов на странице.
        login_url (str): URL для перенаправления при отсутствии авторизации.
    """

    model = Nomination
    template_name = "polls/nomination_list.html"
    context_object_name = "nominations"
    paginate_by = 5
    login_url = "/login/"


class NominationCreateView(AdminRequiredMixin, CreateView):
    """
    Представление для создания новой номинации.

    Права доступа:
        - Только для администраторов (проверка при GET и POST)

    Attributes:
        model (Model): Модель Nomination.
        fields (list): Поля для отображения в форме.
        template_name (str): Путь к шаблону.
        success_url (str): URL для перенаправления после успешного создания.
    """

    model = Nomination
    fields = ["title", "is_active"]
    template_name = "polls/nomination_form.html"
    success_url = reverse_lazy("nomination_list")


class NominationUpdateView(AdminRequiredMixin, UpdateView):
    """
    Представление для редактирования номинации.

    Права доступа:
        - Только для администраторов (проверка при GET и POST)

    Attributes:
        model (Model): Модель Nomination.
        fields (list): Поля для отображения в форме.
        template_name (str): Путь к шаблону.
        success_url (str): URL для перенаправления после успешного обновления.
    """

    model = Nomination
    fields = ["title", "is_active"]
    template_name = "polls/nomination_form.html"
    success_url = reverse_lazy("nomination_list")


class NominationDeleteView(AdminRequiredMixin, DeleteView):
    """
    Представление для удаления номинации.

    Права доступа:
        - Только для администраторов (проверка при GET и POST)

    Attributes:
        model (Model): Модель Nomination.
        template_name (str): Путь к шаблону подтверждения.
        success_url (str): URL для перенаправления после успешного удаления.
    """

    model = Nomination
    template_name = "polls/nomination_confirm_delete.html"
    success_url = reverse_lazy("nomination_list")


class CandidatesByNominationView(LoginRequiredMixin, ListView):
    """
    Представление для отображения кандидатов в конкретной номинации.

    Права доступа:
        - Только для авторизованных пользователей

    Attributes:
        model (Model): Модель Candidate.
        template_name (str): Путь к шаблону.
        context_object_name (str): Имя объекта в контексте.
        paginate_by (int): Количество элементов на странице.
    """

    model = Candidate
    template_name = "polls/candidates_by_nomination.html"
    context_object_name = "candidates"
    paginate_by = 5

    def get_queryset(self) -> QuerySet[Candidate]:
        """
        Возвращает кандидатов для конкретной номинации.

        Returns:
            QuerySet[Candidate]: Кандидаты с подгрузкой связанной номинации.
        """
        nomination_id = self.kwargs.get("nomination_id")
        return Candidate.objects.filter(nomination_id=nomination_id).select_related(
            "nomination"
        )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Добавляет в контекст объект номинации.

        Args:
            **kwargs: Дополнительные аргументы.

        Returns:
            Dict[str, Any]: Контекст с полем 'nomination'.
        """
        context = super().get_context_data(**kwargs)
        context["nomination"] = Nomination.objects.get(pk=self.kwargs["nomination_id"])
        return context


@login_required
def vote_for_candidate(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Обработчик голосования за кандидата.

    Args:
        request: HTTP запрос.
        pk: Идентификатор кандидата.

    Returns:
        HttpResponse: Перенаправление на страницу кандидата.

    Raises:
        Http404: Если кандидат не найден.
    """
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
    """
    Регистрация нового пользователя.

    Args:
        request: HTTP запрос с данными формы регистрации.

    Returns:
        HttpResponse: При успехе - перенаправление на список номинаций,
                      при ошибке - страница регистрации с формой.
    """
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Регистрация успешна! Добро пожаловать!")

            try:
                send_welcome_email.delay(user.id)
            except Exception:
                pass

            return redirect("nomination_list")
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {"form": form})


def test_500_view(request: HttpRequest) -> None:
    """
    Тестовое представление для вызова ошибки 500.

    Args:
        request: HTTP запрос.

    Raises:
        ZeroDivisionError: Всегда вызывает ошибку деления на ноль.
    """
    1 / 0
