import django_filters
from django.db.models import Count

from .models import Candidate


class CandidateFilter(django_filters.FilterSet):
    nomination = django_filters.NumberFilter(field_name='nomination_id')
    has_photo = django_filters.BooleanFilter(method='filter_has_photo')
    has_votes = django_filters.BooleanFilter(method='filter_has_votes',
                                             label="Есть голоса")
    min_votes = django_filters.NumberFilter(method='filter_min_votes',
                                            label="Минимум голосов")
    voted_by_me = django_filters.BooleanFilter(method='filter_voted_by_me',
                                               label="Я голосовал")

    has_jury = django_filters.BooleanFilter(
        method='filter_has_jury',
        label="Есть члены жюри в номинации"
    )

    class Meta:
        model = Candidate
        fields = ['nomination', 'has_photo',
                  'has_votes', 'min_votes', 'voted_by_me']

    def filter_has_jury(self, queryset, name, value):
        if value:
            return queryset.filter(nomination__jury_members__isnull=False).distinct()
        return queryset.filter(nomination__jury_members__isnull=True).distinct()

    def filter_has_photo(self, queryset, name, value):
        if value:
            return queryset.exclude(photo__isnull=True).exclude(photo='')
        return queryset.filter(photo__isnull=True) | queryset.filter(photo='')

    def filter_has_votes(self, queryset, name, value):
        annotated = queryset.annotate(vc=Count('votes'))
        if value:
            return annotated.filter(vc__gt=0)
        return annotated.filter(vc=0)

    def filter_min_votes(self, queryset, name, value):
        return queryset.annotate(vc=Count('votes')).filter(vc__gte=value)

    def filter_voted_by_me(self, queryset, name, value):
        user = self.request.user if hasattr(self.request, 'user') else None
        if not user or not user.is_authenticated:
            return queryset.none() if value else queryset
        if value:
            return queryset.filter(votes__user=user).distinct()
        return queryset.exclude(votes__user=user).distinct()
