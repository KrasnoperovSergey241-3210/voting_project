"""
Модели данных для приложения polls.

Содержит модели:
    - Nomination: Номинация (категория голосования)
    - Candidate: Кандидат в номинации
    - FavoriteCandidate: Избранный кандидат пользователя
    - Vote: Голос пользователя за кандидата
    - JuryMember: Член жюри
"""
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from simple_history.models import HistoricalRecords

User = get_user_model()


class Nomination(models.Model):
    """
    Модель номинации (категории голосования).

    Attributes:
        title (str): Название номинации.
        description (str): Описание номинации.
        is_active (bool): Активна ли номинация для голосования.
        created_at (datetime): Дата и время создания.
        updated_at (datetime): Дата и время последнего обновления.
        created_by (User): Пользователь, создавший номинацию.
        history (HistoricalRecords): История изменений.
    """

    title = models.CharField(max_length=255, verbose_name="Название номинации")
    description = models.TextField(blank=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_nominations",
        verbose_name="Создал",
    )

    history = HistoricalRecords()

    class Meta:
        """Мета-настройки модели."""

        verbose_name = "Номинация"
        verbose_name_plural = "Номинации"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """
        Строковое представление номинации.

        Returns:
            str: Название номинации.
        """
        return self.title


class Candidate(models.Model):
    """
    Модель кандидата в номинации.

    Attributes:
        nomination (Nomination): Номинация, в которой участвует кандидат.
        name (str): Имя кандидата.
        photo (ImageField): Фото кандидата.
        slug (str): Уникальный URL-идентификатор (генерируется автоматически).
        created_at (datetime): Дата и время создания.
        updated_at (datetime): Дата и время последнего обновления.
        created_by (User): Пользователь, создавший кандидата.
        last_modified_by (User): Пользователь, последним редактировавший кандидата.
        history (HistoricalRecords): История изменений.
    """

    nomination = models.ForeignKey(
        Nomination,
        on_delete=models.CASCADE,
        related_name="candidates",
        verbose_name="Номинация",
    )
    name = models.CharField(max_length=255, verbose_name="Имя кандидата")
    photo = models.ImageField(
        upload_to="candidates/%Y/%m/%d/",
        blank=True,
        null=True,
        verbose_name="Фото кандидата",
    )
    slug = models.SlugField(
        max_length=255, unique=True, blank=True, verbose_name="Slug (автогенерируется)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_candidates",
        verbose_name="Создал",
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modified_candidates",
        verbose_name="Последний редактор",
    )

    history = HistoricalRecords()

    class Meta:
        """Мета-настройки модели."""

        verbose_name = "Кандидат"
        verbose_name_plural = "Кандидаты"
        ordering = ["name"]

    def __str__(self) -> str:
        """
        Строковое представление кандидата.

        Returns:
            str: Формат "Имя кандидата (Номинация)".
        """
        return f"{self.name} ({self.nomination})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Сохраняет кандидата с автоматической генерацией slug.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.
                - user: Пользователь, выполняющий сохранение.

        Note:
            - Устанавливает created_by при создании.
            - Устанавливает last_modified_by при обновлении.
            - Генерирует уникальный slug из имени и номинации.
        """
        user = kwargs.pop("user", None)
        if user:
            if not self.pk:
                self.created_by = user
            self.last_modified_by = user

        if not self.slug:
            base = f"{self.name} {self.nomination.title}"
            self.slug = slugify(base)
            original = self.slug
            counter = 1
            while Candidate.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class FavoriteCandidate(models.Model):
    """
    Модель избранного кандидата для пользователя.

    Attributes:
        user (User): Пользователь, добавивший в избранное.
        candidate (Candidate): Кандидат в избранном.
        added_at (datetime): Дата и время добавления.
        note (str): Заметка пользователя о кандидате.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Пользователь"
    )
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, verbose_name="Кандидат"
    )
    added_at = models.DateTimeField(
        default=timezone.now, db_index=True, verbose_name="Добавлено"
    )
    note = models.CharField(max_length=200, blank=True, verbose_name="Заметка")

    class Meta:
        """Мета-настройки модели."""

        verbose_name = "Избранный кандидат"
        verbose_name_plural = "Избранные кандидаты"
        unique_together = ["user", "candidate"]
        ordering = ["-added_at"]

    def __str__(self) -> str:
        """
        Строковое представление избранного кандидата.

        Returns:
            str: Формат "пользователь → кандидат".
        """
        return f"{self.user.username} → {self.candidate.name}"


class Vote(models.Model):
    """
    Модель голоса пользователя за кандидата.

    Attributes:
        user (User): Пользователь, проголосовавший.
        candidate (Candidate): Кандидат, за которого проголосовали.
        created_at (datetime): Дата и время голосования.
        created_by (User): Пользователь, создавший запись.
        history (HistoricalRecords): История изменений.

    Constraints:
        unique_vote_per_candidate: Пользователь не может голосовать дважды
                                   за одного кандидата.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Пользователь"
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name="Кандидат",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Дата голосования"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_votes",
        verbose_name="Создал запись",
    )

    history = HistoricalRecords()

    class Meta:
        """Мета-настройки модели."""

        verbose_name = "Голос"
        verbose_name_plural = "Голоса"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "candidate"], name="unique_vote_per_candidate"
            ),
        ]

    def clean(self) -> None:
        """
        Валидация голоса перед сохранением.

        Raises:
            ValidationError: Если пользователь уже голосовал в этой номинации.

        Note:
            Проверяет, что пользователь не голосовал за другого кандидата
            в той же номинации.
        """
        if (
            Vote.objects.filter(
                user=self.user, candidate__nomination=self.candidate.nomination
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError("Вы уже голосовали в этой номинации")

    def __str__(self) -> str:
        """
        Строковое представление голоса.

        Returns:
            str: Формат "пользователь → кандидат".
        """
        return f"{self.user} → {self.candidate}"


class JuryMember(models.Model):
    """
    Модель члена жюри.

    Attributes:
        name (str): Имя члена жюри.
        nominations (ManyToManyField): Номинации, в которых участвует.
        created_at (datetime): Дата и время создания.
        updated_at (datetime): Дата и время последнего обновления.
        history (HistoricalRecords): История изменений.
    """

    name = models.CharField(max_length=255, verbose_name="Имя члена жюри")
    nominations = models.ManyToManyField(
        Nomination, related_name="jury_members", blank=True, verbose_name="Номинации"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    history = HistoricalRecords()

    class Meta:
        """Мета-настройки модели."""

        verbose_name = "Член жюри"
        verbose_name_plural = "Члены жюри"
        ordering = ["name"]

    def __str__(self) -> str:
        """
        Строковое представление члена жюри.

        Returns:
            str: Имя члена жюри.
        """
        return self.name
