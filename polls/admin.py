from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from import_export import resources
from import_export.admin import ImportExportModelAdmin, ExportMixin
from simple_history.admin import SimpleHistoryAdmin

from .models import Candidate, Nomination, Vote
from .models import JuryMember

class VoteInline(admin.TabularInline):
    model = Vote
    fields = ('user', 'created_at')
    readonly_fields = ('user', 'created_at')
    can_delete = False
    extra = 0

    def has_add_permission(self, request, obj):
        return False

class NominationAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    list_display = ('id', 'title', 'is_active', 'candidates_count', 'created_at')
    list_display_links = ('id', 'title')
    list_filter = ('is_active',)
    search_fields = ('title',)
    readonly_fields = ('created_at', 'updated_at')
    fields = ('title', 'is_active', 'created_at', 'updated_at')

    @admin.display(description="Кол-во кандидатов")
    def candidates_count(self, obj):
        return obj.candidates.count()
    candidates_count.short_description = "Кол-во кандидатов"

@admin.register(Candidate)
class CandidateAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    list_display = ('id', 'name', 'nomination', 'votes_count', 'has_photo', 'photo_preview')
    list_display_links = ('id', 'name')
    list_filter = ('nomination',)
    search_fields = ('name', 'nomination__title')
    raw_id_fields = ('nomination',)
    inlines = (VoteInline,)
    fieldsets = (
        ("Основная информация", {
            "fields": ('name', 'nomination', 'photo')
        }),
    )
    readonly_fields = ('photo_preview',)

    @admin.display(description="Кол-во голосов")
    def votes_count(self, obj):
        return obj.votes.count()
    votes_count.short_description = "Кол-во голосов"

    @admin.display(description="Фото", ordering=False)
    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height: 60px;"/>',
                obj.photo.url
            )
        return "—"
    photo_preview.short_description = "Фото" 

    @admin.display(description="Есть фото", boolean=True)
    def has_photo(self, obj):
        return bool(obj.photo)
    has_photo.short_description = "Есть фото"

class VoteResource(resources.ModelResource):
    class Meta:
        model = Vote
        fields = ('id', 'user', 'candidate', 'created_at')

    def dehydrate_user(self, vote):
        return vote.user.username.upper()

    def dehydrate_candidate(self, vote):
        return f"{vote.candidate.name} ({vote.candidate.nomination.title})"

    def dehydrate_created_at(self, vote):
        """Дополнительная кастомизация даты"""
        return vote.created_at.strftime("%d.%m.%Y %H:%M")

    def get_export_queryset(self, request):
        """Кастомизация queryset для экспорта"""
        return Vote.objects.filter(candidate__nomination__is_active=True)

@admin.register(Vote)
class VoteAdmin(SimpleHistoryAdmin, ExportMixin, admin.ModelAdmin):
    resource_class = VoteResource

    list_display = ('id', 'user', 'candidate', 'created_at', 'candidate_and_user')
    list_display_links = ('id',)
    list_filter = ('candidate__nomination', 'created_at')
    search_fields = ('user__username', 'candidate__name')
    raw_id_fields = ('user', 'candidate')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    @admin.display(description="Кандидат / Пользователь")
    def candidate_and_user(self, obj):
        return f"{obj.candidate.name} — {obj.user.username}"
    candidate_and_user.short_description = "Кандидат / Пользователь"

@admin.register(JuryMember)
class JuryMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    filter_horizontal = ('nominations',)