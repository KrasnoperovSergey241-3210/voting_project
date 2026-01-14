from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import Candidate, Nomination, Vote


@admin.register(Nomination)
class NominationAdmin(ImportExportModelAdmin):
    list_display = ('id', 'title', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title',)


@admin.register(Candidate)
class CandidateAdmin(ImportExportModelAdmin):
    list_display = ('id', 'name', 'nomination')
    list_filter = ('nomination',)
    search_fields = ('name',)


@admin.register(Vote)
class VoteAdmin(ImportExportModelAdmin):
    list_display = ('user', 'candidate', 'created_at')
    list_filter = ('candidate__nomination',)
