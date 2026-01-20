from django.contrib import admin
from django.utils.html import format_html
from import_export import resources
from import_export.admin import ExportMixin, ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import Candidate, JuryMember, Vote


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
    list_display = ('id', 'name', 'nomination', 'votes_count',
                    'has_photo', 'photo_preview')
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
    unique_number = resources.Field(column_name='Уникальный номер',
                                    attribute='id', readonly=True)
    user_field = resources.Field(column_name='Пользователь',
                                 attribute='user', readonly=True)
    candidate_field = resources.Field(column_name='Кандидат',
                                      attribute='candidate', readonly=True)
    created_at_field = resources.Field(column_name='Дата голосования',
                                       attribute='created_at', readonly=True)
    candidate_user_field = resources.Field(column_name='Кандидат / Пользователь',
                                    attribute='candidate_and_user', readonly=True)

    class Meta:
        model = Vote
        fields = ('unique_number', 'user_field', 'candidate_field',
                  'created_at_field', 'candidate_user_field')
        export_order = ('unique_number', 'user_field', 'candidate_field',
                        'created_at_field', 'candidate_user_field')

    def dehydrate_unique_number(self, vote):
        return vote.id

    def dehydrate_user_field(self, vote):
        return vote.user.username.upper() if vote.user and vote.user.username else "-"

    def dehydrate_candidate_field(self, vote):
        if vote.candidate and vote.candidate.nomination:
            return f"{vote.candidate.name} ({vote.candidate.nomination.title})"
        return "-"

    def dehydrate_created_at_field(self, vote):
        return vote.created_at.strftime(
            "%d.%m.%Y %H:%M") if vote.created_at else "-"

    def dehydrate_candidate_user_field(self, vote):
        return \
        f"{vote.candidate.name} — {vote.user.username}" \
            if vote.candidate and vote.user else "-"

    def get_export_queryset(self, request):
        return Vote.objects.filter(
            candidate__nomination__is_active=True).select_related(
            'user', 'candidate__nomination')

@admin.register(Vote)
class VoteAdmin(ExportMixin, SimpleHistoryAdmin, admin.ModelAdmin):
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