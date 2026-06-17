"""
Фильтры для приложения polls.

Содержит кастомный FilterSet для модели Candidate.
"""

import django_filters
from django.contrib.auth import get_user_model
from django.db.models import Count, QuerySet

from .models import Candidate

User = get_user_model()


class CandidateFilter(django_filters.FilterSet):
    """
    Набор фильтров для модели Candidate.

    Фильтры:
        - nomination: по ID номинации
        - has_photo: наличие фото
        - has_votes: наличие голосов
        - min_votes: минимальное количество голосов
        - voted_by_me: голосовал ли текущий пользователь
        - has_jury: наличие членов жюри в номинации

    Attributes:
        nomination (NumberFilter): Фильтр по ID номинации.
        has_photo (BooleanFilter): Фильтр по наличию фото.
        has_votes (BooleanFilter): Фильтр по наличию голосов.
        min_votes (NumberFilter): Фильтр по минимальному количеству голосов.
        voted_by_me (BooleanFilter): Фильтр по голосованию пользователя.
        has_jury (BooleanFilter): Фильтр по наличию членов жюри.
    """

    nomination = django_filters.NumberFilter(field_name="nomination_id")
    has_photo = django_filters.BooleanFilter(method="filter_has_photo")
    has_votes = django_filters.BooleanFilter(
        method="filter_has_votes", label="Есть голоса"
    )
    min_votes = django_filters.NumberFilter(
        method="filter_min_votes", label="Минимум голосов"
    )
    voted_by_me = django_filters.BooleanFilter(
        method="filter_voted_by_me", label="Я голосовал"
    )
    has_jury = django_filters.BooleanFilter(
        method="filter_has_jury", label="Есть члены жюри в номинации"
    )

    class Meta:
        model = Candidate
        fields = ["nomination", "has_photo", "has_votes", "min_votes", "voted_by_me"]

    def filter_has_jury(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """
        Фильтрует кандидатов по наличию членов жюри в номинации.

        Args:
            queryset: Исходный queryset.
            name: Имя поля (не используется).
            value: True - есть члены жюри, False - нет.

        Returns:
            QuerySet: Отфильтрованный queryset.
        """
        if value:
            return queryset.filter(nomination__jury_members__isnull=False).distinct()
        return queryset.filter(nomination__jury_members__isnull=True).distinct()

    def filter_has_photo(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """
        Фильтрует кандидатов по наличию фото.

        Args:
            queryset: Исходный queryset.
            name: Имя поля (не используется).
            value: True - есть фото, False - нет фото.

        Returns:
            QuerySet: Отфильтрованный queryset.
        """
        if value:
            return queryset.exclude(photo__isnull=True).exclude(photo="")
        return queryset.filter(photo__isnull=True) | queryset.filter(photo="")

    def filter_has_votes(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """
        Фильтрует кандидатов по наличию голосов.

        Args:
            queryset: Исходный queryset.
            name: Имя поля (не используется).
            value: True - есть голоса, False - нет голосов.

        Returns:
            QuerySet: Отфильтрованный queryset с аннотацией vote_count.
        """
        annotated = queryset.annotate(vc=Count("votes"))
        if value:
            return annotated.filter(vc__gt=0)
        return annotated.filter(vc=0)

    def filter_min_votes(self, queryset: QuerySet, name: str, value: int) -> QuerySet:
        """
        Фильтрует кандидатов по минимальному количеству голосов.

        Args:
            queryset: Исходный queryset.
            name: Имя поля (не используется).
            value: Минимальное количество голосов.

        Returns:
            QuerySet: Отфильтрованный queryset с аннотацией vote_count.
        """
        return queryset.annotate(vc=Count("votes")).filter(vc__gte=value)

    def filter_voted_by_me(
        self, queryset: QuerySet, name: str, value: bool
    ) -> QuerySet:
        """
        Фильтрует кандидатов по голосованию текущего пользователя.

        Args:
            queryset: Исходный queryset.
            name: Имя поля (не используется).
            value: True - только те, за кого голосовал пользователь,
                   False - только те, за кого не голосовал.

        Returns:
            QuerySet: Отфильтрованный queryset.

        Note:
            Если пользователь не авторизован, возвращает пустой queryset.
        """
        user = self.request.user if hasattr(self.request, "user") else None
        if not user or not user.is_authenticated:
            return queryset.none() if value else queryset
        if value:
            return queryset.filter(votes__user=user).distinct()
        return queryset.exclude(votes__user=user).distinct()
