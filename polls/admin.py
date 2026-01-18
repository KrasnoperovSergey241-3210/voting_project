from django.contrib import admin
from django.utils.html import format_html
from import_export import resources
from import_export.admin import ExportMixin, ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import Candidate, JuryMember, Nomination, Vote


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
        return super().get_export_queryset(request).filter(
            candidate__nomination__is_active=True
        ).select_related('candidate__nomination', 'user')

class VoteInline(admin.TabularInline):
    model = Vote
    extra = 0
    readonly_fields = ('user', 'created_at')
    raw_id_fields = ('user',)


@admin.register(Nomination)
class NominationAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    list_display = ('id', 'title', 'is_active', 'candidates_count')
    list_display_links = ('id', 'title')
    list_filter = ('is_active',)
    search_fields = ('title',)
    readonly_fields = ()
    ordering = ('title',)

    @admin.display(description="Кол-во кандидатов")
    def candidates_count(self, obj):
        return obj.candidates.count()
    
    list_display = ('id', 'title', 'is_active', 'candidates_count', 'created_at')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Candidate)
class CandidateAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    list_display = ('id', 'name', 'nomination', 
                    'votes_count', 'has_photo', 'photo_preview')
    list_display_links = ('id', 'name')
    list_filter = ('nomination',)
    search_fields = ('name', 'nomination__title')
    inlines = (VoteInline,)

    fieldsets = (
        ("Основная информация", {
            "fields": ('name', 'nomination', 'photo', 'slug')
        }),
    )

    @admin.display(description="Кол-во голосов")
    def votes_count(self, obj):
        return obj.votes.count()

    @admin.display(description="Фото", ordering=False)
    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height: 60px;"/>',
                obj.photo.url
            )
        return "—"

    @admin.display(description="Есть фото", boolean=True)
    def has_photo(self, obj):
        return bool(obj.photo)

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

@admin.register(JuryMember)
class JuryMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    filter_horizontal = ('nominations',)