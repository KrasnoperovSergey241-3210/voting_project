from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from import_export import resources
from import_export.admin import ExportMixin, ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import Candidate, JuryMember, Nomination, Vote


class UserAdmin(BaseUserAdmin):
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
    model = Vote
    fields = ("user", "created_at")
    readonly_fields = ("user", "created_at")
    can_delete = False
    extra = 0

    def has_add_permission(self, request, obj):
        return False


class NominationAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    list_display = ("id", "title", "is_active", "candidates_count", "created_at")
    list_display_links = ("id", "title")
    list_filter = ("is_active",)
    search_fields = ("title",)
    readonly_fields = ("created_at", "updated_at")
    fields = ("title", "is_active", "created_at", "updated_at")

    @admin.display(description="Кол-во кандидатов")
    def candidates_count(self, obj):
        return obj.candidates.count()


@admin.register(Candidate)
class CandidateAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
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
    def votes_count(self, obj):
        return obj.votes.count()

    @admin.display(description="Фото", ordering=False)
    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height: 60px;"/>', obj.photo.url
            )
        return "—"

    @admin.display(description="Есть фото", boolean=True)
    def has_photo(self, obj):
        return bool(obj.photo)


class VoteResource(resources.ModelResource):
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

    def dehydrate_unique_number(self, vote):
        return vote.id

    def dehydrate_user_field(self, vote):
        return vote.user.username.upper() if vote.user and vote.user.username else "-"

    def dehydrate_candidate_field(self, vote):
        if vote.candidate and vote.candidate.nomination:
            return f"{vote.candidate.name} ({vote.candidate.nomination.title})"
        return "-"

    def dehydrate_created_at_field(self, vote):
        return vote.created_at.strftime("%d.%m.%Y %H:%M") if vote.created_at else "-"

    def dehydrate_candidate_user_field(self, vote):
        return (
            f"{vote.candidate.name} — {vote.user.username}"
            if vote.candidate and vote.user
            else "-"
        )

    def get_export_queryset(self, request):
        return Vote.objects.filter(
            candidate__nomination__is_active=True
        ).select_related("user", "candidate__nomination")


@admin.register(Vote)
class VoteAdmin(ExportMixin, SimpleHistoryAdmin, admin.ModelAdmin):
    resource_class = VoteResource

    list_display = ("id", "user", "candidate", "created_at", "candidate_and_user")
    list_display_links = ("id",)
    list_filter = ("candidate__nomination", "created_at")
    search_fields = ("user__username", "candidate__name")
    raw_id_fields = ("user", "candidate")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    @admin.display(description="Кандидат / Пользователь")
    def candidate_and_user(self, obj):
        return f"{obj.candidate.name} — {obj.user.username}"


@admin.register(JuryMember)
class JuryMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    filter_horizontal = ("nominations",)


admin.site.register(Nomination, NominationAdmin)
