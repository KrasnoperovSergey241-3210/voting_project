"""
Настройки административной панели для приложения polls.

Содержит админ-классы для моделей:
    - UserAdmin: настройки для пользователей
    - NominationAdmin: настройки для номинаций
    - CandidateAdmin: настройки для кандидатов
    - VoteAdmin: настройки для голосов
    - JuryMemberAdmin: настройки для членов жюри
"""
from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils.html import format_html
from import_export import resources
from import_export.admin import ExportMixin, ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import Candidate, JuryMember, Nomination, Vote


class UserAdmin(BaseUserAdmin):
    """
    Настройки административной панели для модели User.

    Attributes:
        list_display (tuple): Отображаемые поля в списке.
        list_filter (tuple): Поля для фильтрации.
        search_fields (tuple): Поля для поиска.
        fieldsets (tuple): Группы полей в форме редактирования.
        add_fieldsets (tuple): Группы полей в форме создания.
    """

    list_display = ("username", "email", "first_name", "last_name", "is_staff")
    list_filter = ("is_staff", "is_active")
    search_fields = ("username", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Персональная информация", {"fields": ("first_name", "last_name", "email")}),
        (
            "Права доступа",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class VoteInline(admin.TabularInline):
    """
    Inline-форма для отображения голосов в карточке кандидата.

    Attributes:
        model (Model): Модель Vote.
        fields (tuple): Отображаемые поля.
        readonly_fields (tuple): Поля только для чтения.
        can_delete (bool): Разрешено ли удаление.
        extra (int): Количество пустых форм.
    """

    model = Vote
    fields = ("user", "created_at")
    readonly_fields = ("user", "created_at")
    can_delete = False
    extra = 0

    def has_add_permission(self, request: HttpRequest, obj: Any) -> bool:
        """
        Запрещает добавление голосов через инлайн.

        Args:
            request: HTTP запрос.
            obj: Объект родительской модели.

        Returns:
            bool: Всегда False.
        """
        return False


class NominationAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    """
    Настройки административной панели для модели Nomination.

    Attributes:
        list_display (tuple): Отображаемые поля в списке.
        list_display_links (tuple): Поля-ссылки на детальную страницу.
        list_filter (tuple): Поля для фильтрации.
        search_fields (tuple): Поля для поиска.
        readonly_fields (tuple): Поля только для чтения.
        fields (tuple): Отображаемые поля в форме.
    """

    list_display = ("id", "title", "is_active", "candidates_count", "created_at")
    list_display_links = ("id", "title")
    list_filter = ("is_active",)
    search_fields = ("title",)
    readonly_fields = ("created_at", "updated_at")
    fields = ("title", "is_active", "created_at", "updated_at")

    @admin.display(description="Кол-во кандидатов")
    def candidates_count(self, obj: Nomination) -> int:
        """
        Возвращает количество кандидатов в номинации.

        Args:
            obj: Объект номинации.

        Returns:
            int: Количество кандидатов.
        """
        return obj.candidates.count()


@admin.register(Candidate)
class CandidateAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    """
    Настройки административной панели для модели Candidate.

    Attributes:
        list_display (tuple): Отображаемые поля в списке.
        list_display_links (tuple): Поля-ссылки на детальную страницу.
        list_filter (tuple): Поля для фильтрации.
        search_fields (tuple): Поля для поиска.
        raw_id_fields (tuple): Поля с выбором по ID.
        inlines (tuple): Inline-формы.
        fieldsets (tuple): Группы полей в форме редактирования.
        readonly_fields (tuple): Поля только для чтения.
    """

    list_display = (
        "id",
        "name",
        "nomination",
        "votes_count",
        "has_photo",
        "photo_preview",
    )
    list_display_links = ("id", "name")
    list_filter = ("nomination",)
    search_fields = ("name", "nomination__title")
    raw_id_fields = ("nomination",)
    inlines = (VoteInline,)
    fieldsets = (("Основная информация", {"fields": ("name", "nomination", "photo")}),)
    readonly_fields = ("photo_preview",)

    @admin.display(description="Кол-во голосов")
    def votes_count(self, obj: Candidate) -> int:
        """
        Возвращает количество голосов за кандидата.

        Args:
            obj: Объект кандидата.

        Returns:
            int: Количество голосов.
        """
        return obj.votes.count()

    @admin.display(description="Фото", ordering=False)
    def photo_preview(self, obj: Candidate) -> str:
        """
        Возвращает HTML-превью фото кандидата.

        Args:
            obj: Объект кандидата.

        Returns:
            str: HTML-код с изображением или прочерк.
        """
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height: 60px;"/>', obj.photo.url
            )
        return "—"

    @admin.display(description="Есть фото", boolean=True)
    def has_photo(self, obj: Candidate) -> bool:
        """
        Проверяет наличие фото у кандидата.

        Args:
            obj: Объект кандидата.

        Returns:
            bool: True если есть фото, иначе False.
        """
        return bool(obj.photo)


class VoteResource(resources.ModelResource):
    """
    Ресурс для экспорта голосов в Excel.

    Attributes:
        unique_number (Field): Уникальный номер голоса.
        user_field (Field): Пользователь.
        candidate_field (Field): Кандидат.
        created_at_field (Field): Дата голосования.
        candidate_user_field (Field): Кандидат / Пользователь.
    """

    unique_number = resources.Field(
        column_name="Уникальный номер", attribute="id", readonly=True
    )
    user_field = resources.Field(
        column_name="Пользователь", attribute="user", readonly=True
    )
    candidate_field = resources.Field(
        column_name="Кандидат", attribute="candidate", readonly=True
    )
    created_at_field = resources.Field(
        column_name="Дата голосования", attribute="created_at", readonly=True
    )
    candidate_user_field = resources.Field(
        column_name="Кандидат / Пользователь",
        attribute="candidate_and_user",
        readonly=True,
    )

    class Meta:
        model = Vote
        fields = (
            "unique_number",
            "user_field",
            "candidate_field",
            "created_at_field",
            "candidate_user_field",
        )
        export_order = (
            "unique_number",
            "user_field",
            "candidate_field",
            "created_at_field",
            "candidate_user_field",
        )

    def dehydrate_unique_number(self, vote: Vote) -> int:
        """
        Возвращает ID голоса.

        Args:
            vote: Объект голоса.

        Returns:
            int: ID голоса.
        """
        return vote.id

    def dehydrate_user_field(self, vote: Vote) -> str:
        """
        Возвращает имя пользователя в верхнем регистре.

        Args:
            vote: Объект голоса.

        Returns:
            str: Имя пользователя или прочерк.
        """
        return vote.user.username.upper() if vote.user and vote.user.username else "-"

    def dehydrate_candidate_field(self, vote: Vote) -> str:
        """
        Возвращает имя кандидата с номинацией.

        Args:
            vote: Объект голоса.

        Returns:
            str: Формат "Имя кандидата (Номинация)" или прочерк.
        """
        if vote.candidate and vote.candidate.nomination:
            return f"{vote.candidate.name} ({vote.candidate.nomination.title})"
        return "-"

    def dehydrate_created_at_field(self, vote: Vote) -> str:
        """
        Возвращает дату голосования в формате DD.MM.YYYY HH:MM.

        Args:
            vote: Объект голоса.

        Returns:
            str: Отформатированная дата или прочерк.
        """
        return vote.created_at.strftime("%d.%m.%Y %H:%M") if vote.created_at else "-"

    def dehydrate_candidate_user_field(self, vote: Vote) -> str:
        """
        Возвращает комбинацию кандидата и пользователя.

        Args:
            vote: Объект голоса.

        Returns:
            str: Формат "Кандидат — Пользователь" или прочерк.
        """
        return (
            f"{vote.candidate.name} — {vote.user.username}"
            if vote.candidate and vote.user
            else "-"
        )

    def get_export_queryset(self, request: HttpRequest) -> Any:
        """
        Возвращает queryset для экспорта (только активные номинации).

        Args:
            request: HTTP запрос.

        Returns:
            QuerySet: Отфильтрованный queryset голосов.
        """
        return Vote.objects.filter(
            candidate__nomination__is_active=True
        ).select_related("user", "candidate__nomination")


@admin.register(Vote)
class VoteAdmin(ExportMixin, SimpleHistoryAdmin, admin.ModelAdmin):
    """
    Настройки административной панели для модели Vote.

    Attributes:
        resource_class (Resource): Класс ресурса для экспорта.
        list_display (tuple): Отображаемые поля в списке.
        list_display_links (tuple): Поля-ссылки на детальную страницу.
        list_filter (tuple): Поля для фильтрации.
        search_fields (tuple): Поля для поиска.
        raw_id_fields (tuple): Поля с выбором по ID.
        readonly_fields (tuple): Поля только для чтения.
        date_hierarchy (str): Поле для иерархии по дате.
    """

    resource_class = VoteResource

    list_display = ("id", "user", "candidate", "created_at", "candidate_and_user")
    list_display_links = ("id",)
    list_filter = ("candidate__nomination", "created_at")
    search_fields = ("user__username", "candidate__name")
    raw_id_fields = ("user", "candidate")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    @admin.display(description="Кандидат / Пользователь")
    def candidate_and_user(self, obj: Vote) -> str:
        """
        Возвращает комбинацию кандидата и пользователя.

        Args:
            obj: Объект голоса.

        Returns:
            str: Формат "Кандидат — Пользователь".
        """
        return f"{obj.candidate.name} — {obj.user.username}"


@admin.register(JuryMember)
class JuryMemberAdmin(admin.ModelAdmin):
    """
    Настройки административной панели для модели JuryMember.

    Attributes:
        list_display (tuple): Отображаемые поля в списке.
        search_fields (tuple): Поля для поиска.
        filter_horizontal (tuple): Поля с горизонтальным фильтром для ManyToMany.
    """

    list_display = ("id", "name")
    search_fields = ("name",)
    filter_horizontal = ("nominations",)


admin.site.register(Nomination, NominationAdmin)
