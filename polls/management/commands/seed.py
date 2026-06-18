"""
Management команда для заполнения базы данных тестовыми данными.

Создает:
    - 125 пользователей (user1...user125) с email и паролем
    - 25 номинаций (Номинация 1...Номинация 25)
    - 125 кандидатов (по 5 на каждую номинацию)
    - 125 голосов (по 1 на каждого пользователя, случайный кандидат)

Usage:
    python manage.py seed
    python manage.py seed --users=50 --nominations=10
    python manage.py seed --clear
"""

import os
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from polls.models import Candidate, Nomination, Vote

User = get_user_model()


class Command(BaseCommand):
    """
    Команда для заполнения БД тестовыми данными.
    """

    help = "Заполняет БД тестовыми данными (юзеры, номинации, кандидаты, голосы)"

    def add_arguments(self, parser: CommandParser) -> None:
        """
        Добавляет аргументы командной строки.

        Args:
            parser: Парсер аргументов.
        """
        parser.add_argument(
            "--users",
            type=int,
            default=125,
            help="Количество пользователей для создания (по умолчанию: 125)",
        )
        parser.add_argument(
            "--nominations",
            type=int,
            default=25,
            help="Количество номинаций для создания (по умолчанию: 25)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Очистить все данные перед заполнением",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Принудительно выполнить очистку без подтверждения",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Основной метод выполнения команды.

        Args:
            *args: Позиционные аргументы.
            **options: Именованные аргументы.
        """
        users_count: int = options.get("users", 125)
        nominations_count: int = options.get("nominations", 25)
        clear: bool = options.get("clear", False)
        force: bool = options.get("force", False)

        if clear:
            self._clear_data(force)

        with transaction.atomic():
            self._create_users(users_count)
            self._create_nominations(nominations_count)
            self._create_candidates()
            self._create_votes()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nГотово! Создано:\n"
                f"   - Пользователей: {users_count}\n"
                f"   - Номинаций: {nominations_count}\n"
                f"   - Кандидатов: {nominations_count * 5}\n"
                f"   - Голосов: {users_count}"
            )
        )

    def _clear_data(self, force: bool = False) -> None:
        """
        Очищает все данные из таблиц.

        Args:
            force: Если True, очистка выполняется без подтверждения.
        """
        if not force:
            confirm = input("Вы уверены, что хотите удалить все данные? (y/N): ")
            if confirm.lower() != "y":
                self.stdout.write(self.style.WARNING("Очистка отменена."))
                return

        Vote.objects.all().delete()
        Candidate.objects.all().delete()
        Nomination.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()

        self.stdout.write(self.style.SUCCESS("Все тестовые данные удалены."))

    def _create_users(self, count: int) -> None:
        """
        Создает указанное количество пользователей.

        Args:
            count: Количество пользователей для создания.
        """
        self.stdout.write(f"Создание {count} пользователей...")

        existing_users = set(
            User.objects.filter(username__startswith="user").values_list(
                "username", flat=True
            )
        )

        created = 0
        for i in range(1, count + 1):
            username = f"user{i}"
            if username in existing_users:
                continue

            User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password=f"{username}password",
            )
            created += 1

        self.stdout.write(f"   Создано {created} пользователей")

    def _create_nominations(self, count: int) -> None:
        """
        Создает указанное количество номинаций.

        Args:
            count: Количество номинаций для создания.
        """
        self.stdout.write(f"Создание {count} номинаций...")

        existing = set(
            Nomination.objects.filter(title__startswith="Номинация").values_list(
                "title", flat=True
            )
        )

        created = 0
        for i in range(count, 0, -1):
            title = f"Номинация {i}"
            if title in existing:
                continue

            Nomination.objects.create(
                title=title,
                description=f"Описание номинации {i}",
                is_active=True,
            )
            created += 1

        self.stdout.write(f"   Создано {created} номинаций")

    def _create_candidates(self) -> None:
        """
        Создает по 5 кандидатов для каждой номинации с фото из static.
        """
        self.stdout.write("Создание кандидатов...")

        nominations = list(Nomination.objects.all())
        if not nominations:
            msg = "Нет номинаций для создания кандидатов"
            self.stdout.write(self.style.WARNING(msg))
            return

        static_photo_path = os.path.join(settings.BASE_DIR, "static", "photo.jpg")

        if not os.path.exists(static_photo_path):
            self.stdout.write(
                self.style.WARNING(f"Фото не найдено: {static_photo_path}")
            )
            return

        existing = set(
            Candidate.objects.filter(name__startswith="Кандидат").values_list(
                "name", flat=True
            )
        )

        created = 0
        for nomination in nominations:
            for j in range(1, 6):
                name = f"Кандидат {nomination.id}-{j}"
                if name in existing:
                    continue

                candidate = Candidate(
                    nomination=nomination,
                    name=name,
                )

                candidate.save()

                with open(static_photo_path, "rb") as f:
                    candidate.photo.save(
                        f"candidate_{candidate.id}.jpg", File(f), save=True
                    )

                created += 1

        self.stdout.write(f"Создано {created} кандидатов с фото")

    def _create_votes(self) -> None:
        """
        Создает по одному голосу для каждого пользователя за случайного кандидата.
        """
        self.stdout.write("Создание голосов...")

        users = list(User.objects.filter(is_superuser=False))
        candidates = list(Candidate.objects.all())

        if not users:
            self.stdout.write(self.style.WARNING("Нет пользователей для голосования"))
            return

        if not candidates:
            self.stdout.write(self.style.WARNING("Нет кандидатов для голосования"))
            return

        created = 0
        from random import randrange

        for user in users:
            candidate = candidates[randrange(len(candidates))]

            if Vote.objects.filter(
                user=user, candidate__nomination=candidate.nomination
            ).exists():
                continue

            Vote.objects.create(
                user=user,
                candidate=candidate,
                created_by=user,
            )
            created += 1

        self.stdout.write(f"   Создано {created} голосов")
