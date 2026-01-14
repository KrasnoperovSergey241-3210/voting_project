from django.core.management.base import BaseCommand

from polls.models import Candidate


class Command(BaseCommand):
    help = 'Пересчитать количество голосов у кандидатов'

    def handle(self, *args, **options):
        self.stdout.write('Подсчет голосов:')

        for candidate in Candidate.objects.all():
            votes_count = candidate.votes.count()
            self.stdout.write(
                f'- {candidate.name}: {votes_count}'
            )

        self.stdout.write(
            self.style.SUCCESS('Готово!')
        )
