from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from simple_history.models import HistoricalRecords

User = get_user_model()

class Nomination(models.Model):
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
        related_name='created_nominations',
        verbose_name="Создал"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Номинация"
        verbose_name_plural = "Номинации"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Candidate(models.Model):
    nomination = models.ForeignKey(
        Nomination, on_delete=models.CASCADE, 
        related_name='candidates', verbose_name="Номинация"
    )
    name = models.CharField(max_length=255, verbose_name="Имя кандидата")
    photo = models.ImageField(
        upload_to='candidates/%Y/%m/%d/', 
        blank=True, null=True, verbose_name="Фото кандидата"
    )
    slug = models.SlugField(max_length=255, unique=True, 
                            blank=True, verbose_name="Slug (автогенерируется)")
    created_at = models.DateTimeField(auto_now_add=True, 
                                      verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_candidates',
        verbose_name="Создал"
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_candidates',
        verbose_name="Последний редактор"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Кандидат"
        verbose_name_plural = "Кандидаты"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.nomination})"

    def save(self, *args, **kwargs):
        user = kwargs.pop('user', None)
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, 
                             verbose_name="Пользователь")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, 
                                  verbose_name="Кандидат")
    added_at = models.DateTimeField(default=timezone.now, db_index=True, 
                                    verbose_name="Добавлено")
    note = models.CharField(max_length=200, blank=True, verbose_name="Заметка")

    class Meta:
        verbose_name = "Избранный кандидат"
        verbose_name_plural = "Избранные кандидаты"
        unique_together = ['user', 'candidate']
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} → {self.candidate.name}"

class Vote(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name="Кандидат"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата голосования"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_votes',
        verbose_name="Создал запись"
    )
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Голос"
        verbose_name_plural = "Голоса"
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'candidate'],
                name='unique_vote_per_candidate'
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if Vote.objects.filter(
            user=self.user,
            candidate__nomination=self.candidate.nomination
        ).exclude(pk=self.pk).exists():
            raise ValidationError(
                "Вы уже голосовали в этой номинации"
            )

    def __str__(self):
        return f"{self.user} → {self.candidate}"
    
class JuryMember(models.Model):
    name = models.CharField(
        max_length=255,
        verbose_name="Имя члена жюри"
    )
    nominations = models.ManyToManyField(
        Nomination,
        related_name='jury_members',
        blank=True,
        verbose_name="Номинации"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлено"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Член жюри"
        verbose_name_plural = "Члены жюри"
        ordering = ['name']

    def __str__(self):
        return self.name