"""
Сериализаторы для приложения polls.

Содержит сериализаторы для моделей:
    - NominationSerializer
    - CandidateSerializer
    - VoteSerializer
    - JuryMemberSerializer
"""

from typing import Any, Dict, Optional

from django.utils import timezone
from rest_framework import serializers

from .models import Candidate, JuryMember, Nomination, Vote


class NominationSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Nomination.

    Attributes:
        Meta.fields: Все поля модели.
        Meta.read_only_fields: Поля только для чтения.
    """

    class Meta:
        model = Nomination
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "created_by")

    def validate_title(self, value: str) -> str:
        """
        Валидация названия номинации.

        Args:
            value: Название номинации.

        Returns:
            str: Валидное название.

        Raises:
            serializers.ValidationError: Если название уже существует
                                         или короче 3 символов.
        """
        if Nomination.objects.filter(title=value).exists():
            raise serializers.ValidationError(
                "Номинация с таким названием уже существует"
            )
        if len(value) < 3:
            raise serializers.ValidationError(
                "Название номинации должно содержать минимум 3 символа"
            )
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидация данных номинации.

        Args:
            attrs: Словарь с данными для валидации.

        Returns:
            Dict[str, Any]: Валидные данные.

        Raises:
            serializers.ValidationError: Если дата обновления раньше даты создания.

        Note:
            Проверяет, что updated_at > created_at при обновлении.
        """
        if self.instance:
            created_at = self.instance.created_at
            updated_at = attrs.get("updated_at", timezone.now())
            if created_at and updated_at and created_at >= updated_at:
                raise serializers.ValidationError(
                    "Дата обновления должна быть позже даты создания"
                )
        return attrs


class CandidateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Candidate.

    Добавляет дополнительные поля:
        - nomination: вложенный сериализатор номинации (только для чтения)
        - nomination_id: ID номинации для записи
        - photo_url: URL фото кандидата
        - is_favorite: находится ли кандидат в избранном у пользователя
        - vote_count: количество голосов
        - favorites_count: количество добавлений в избранное

    Attributes:
        nomination (NominationSerializer): Вложенный сериализатор.
        nomination_id (PrimaryKeyRelatedField): ID номинации для записи.
        photo_url (SerializerMethodField): URL фото.
        is_favorite (SerializerMethodField): Флаг избранного.
        vote_count (IntegerField): Количество голосов.
        favorites_count (IntegerField): Количество избранных.
    """

    nomination = NominationSerializer(read_only=True)
    nomination_id = serializers.PrimaryKeyRelatedField(
        source="nomination",
        queryset=Nomination.objects.all(),
        write_only=True,
        required=False,
    )
    photo_url = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    vote_count = serializers.IntegerField(read_only=True)
    favorites_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Candidate
        fields = (
            "id",
            "nomination",
            "nomination_id",
            "name",
            "photo",
            "photo_url",
            "slug",
            "created_at",
            "updated_at",
            "created_by",
            "last_modified_by",
            "is_favorite",
            "vote_count",
            "favorites_count",
        )
        read_only_fields = (
            "created_at",
            "updated_at",
            "created_by",
            "last_modified_by",
            "slug",
        )

    def get_photo_url(self, obj: Candidate) -> Optional[str]:
        """
        Возвращает URL фото кандидата.

        Args:
            obj: Объект кандидата.

        Returns:
            Optional[str]: URL фото или None, если фото отсутствует.
        """
        if obj.photo:
            return obj.photo.url
        return None

    def get_is_favorite(self, obj: Candidate) -> bool:
        """
        Проверяет, добавлен ли кандидат в избранное у текущего пользователя.

        Args:
            obj: Объект кандидата.

        Returns:
            bool: True если кандидат в избранном, иначе False.

        Note:
            Использует контекст 'favorites' переданный из view.
        """
        favorites = self.context.get("favorites", [])
        return obj.id in favorites

    def validate_name(self, value: str) -> str:
        """
        Валидация имени кандидата.

        Args:
            value: Имя кандидата.

        Returns:
            str: Валидное имя.

        Raises:
            serializers.ValidationError: Если имя короче 2 символов.
        """
        if len(value) < 2:
            raise serializers.ValidationError(
                "Имя кандидата должно содержать минимум 2 символа"
            )
        return value


class VoteSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Vote.

    Attributes:
        Meta.fields: Поля для сериализации.
        Meta.read_only_fields: Поля только для чтения.
    """

    class Meta:
        model = Vote
        fields = ("id", "candidate", "created_at")
        read_only_fields = ("created_at",)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидация голоса.

        Args:
            attrs: Словарь с данными для валидации.

        Returns:
            Dict[str, Any]: Валидные данные.

        Raises:
            serializers.ValidationError: Если:
                - номинация неактивна
                - пользователь уже голосовал в этой номинации

        Note:
            Проверяет бизнес-логику голосования.
        """
        user = self.context["request"].user
        candidate = attrs["candidate"]

        if not candidate.nomination.is_active:
            raise serializers.ValidationError("Голосование в этой номинации закрыто")

        if Vote.objects.filter(
            user=user, candidate__nomination=candidate.nomination
        ).exists():
            raise serializers.ValidationError("Вы уже голосовали в этой номинации")

        vote = Vote(user=user, candidate=candidate)
        vote.clean()

        return attrs


class JuryMemberSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели JuryMember.

    Attributes:
        nominations (PrimaryKeyRelatedField): Список ID номинаций.
    """

    nominations = serializers.PrimaryKeyRelatedField(
        queryset=Nomination.objects.all(), many=True
    )

    class Meta:
        model = JuryMember
        fields = ("id", "name", "nominations")
