import django_filters

from .models import Candidate


class CandidateFilter(django_filters.FilterSet):
    nomination = django_filters.NumberFilter(
        field_name='nomination_id'
    )

    class Meta:
        model = Candidate
        fields = ['nomination']
