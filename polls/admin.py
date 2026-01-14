from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import Candidate, Nomination, Vote

from import_export import resources
from import_export.admin import ExportMixin

class VoteResource(resources.ModelResource):
    class Meta:
        model = Vote

    def dehydrate_user(self, vote):
        return vote.user.username.upper()

    def dehydrate_candidate(self, vote):
        return f"{vote.candidate.name} ({vote.candidate.nomination.title})"

    def get_export_queryset(self, request):
        return super().get_export_queryset(request).filter(
            candidate__nomination__is_active=True
        )

@admin.register(Nomination)
class NominationAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    list_display = ('id', 'title', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title',)

class VoteInline(admin.TabularInline):
    model = Vote
    extra = 0
    readonly_fields = ('user', 'created_at')

@admin.register(Candidate)
class CandidateAdmin(SimpleHistoryAdmin, ImportExportModelAdmin):
    list_display = ('name', 'nomination', 'vote_count')
    list_filter = ('nomination',)
    fields = ('name', 'nomination')
    inlines = [VoteInline]

    def vote_count(self, obj):
        return obj.votes.count()
    vote_count.short_description = "Number of votes"


@admin.register(Vote)
class VoteAdmin(SimpleHistoryAdmin, ExportMixin, admin.ModelAdmin):
    resource_class = VoteResource
    list_display = ('user', 'candidate', 'created_at', 'custom_field')
    list_filter = ('candidate__nomination',)
    fields = ('user', 'candidate', 'created_at')
    
    def custom_field(self, obj):
        return f"{obj.candidate.name} ({obj.user.username})"
    custom_field.short_description = "Candidate & User"
