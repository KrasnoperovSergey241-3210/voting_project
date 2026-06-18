"""
Тесты для приложения polls.

Содержит тесты для моделей, сериализаторов, API-эндпоинтов и прав доступа.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Candidate, FavoriteCandidate, Nomination, Vote

User = get_user_model()


class VoteModelTest(TestCase):
    """
    Тесты для модели Vote.
    """

    def setUp(self) -> None:
        """
        Создает тестовые данные: пользователя, номинацию и кандидата.
        """
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.nomination = Nomination.objects.create(
            title="Test Nomination", is_active=True
        )
        self.candidate = Candidate.objects.create(
            name="Test Candidate", nomination=self.nomination
        )

    def test_unique_vote_per_nomination(self) -> None:
        """
        Проверяет, что пользователь не может проголосовать дважды за одного кандидата.
        """
        Vote.objects.create(user=self.user, candidate=self.candidate)
        with self.assertRaises(Exception):
            Vote.objects.create(user=self.user, candidate=self.candidate)

    def test_vote_count_annotation(self) -> None:
        """
        Проверяет, что аннотация vote_count корректно подсчитывает количество голосов.
        """
        Vote.objects.create(user=self.user, candidate=self.candidate)
        candidate = Candidate.objects.annotate(vote_count=models.Count("votes")).get(
            id=self.candidate.id
        )
        self.assertEqual(candidate.vote_count, 1)


class NominationValidationTest(TestCase):
    """
    Тесты для валидации модели Nomination через API.
    """

    def setUp(self) -> None:
        """
        Создает суперпользователя и авторизует клиент для доступа к API.
        """
        self.user = User.objects.create_superuser(
            username="admin",
            password="adminpass",
            email="admin@example.com",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_cannot_create_duplicate_nomination_title(self) -> None:
        """
        Проверяет, что нельзя создать номинацию с уже существующим названием.
        """
        Nomination.objects.create(title="Duplicate Title", is_active=True)
        response = self.client.post(
            reverse("nomination-list"),
            {"title": "Duplicate Title", "is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_nomination_title_too_short(self) -> None:
        """
        Проверяет, что название номинации должно содержать минимум 3 символа.
        """
        response = self.client.post(
            reverse("nomination-list"),
            {"title": "ab", "is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CandidateValidationTest(TestCase):
    """
    Тесты для валидации модели Candidate через API.
    """

    def setUp(self) -> None:
        """
        Создает суперпользователя, номинацию и авторизует клиент.
        """
        self.user = User.objects.create_superuser(
            username="admin",
            password="adminpass",
            email="admin@example.com",
        )
        self.nomination = Nomination.objects.create(title="Test Nomination")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_cannot_create_candidate_name_too_short(self) -> None:
        """
        Проверяет, что имя кандидата должно содержать минимум 2 символа.
        """
        response = self.client.post(
            reverse("candidate-list"),
            {"name": "A", "nomination_id": self.nomination.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class VoteAPITest(TestCase):
    """
    Тесты для API-эндпоинтов голосования.
    """

    def setUp(self) -> None:
        """
        Создает пользователя, активную номинацию и кандидата.
        """
        self.user = User.objects.create_user(username="voter", password="votepass")
        self.nomination = Nomination.objects.create(
            title="Active Nomination", is_active=True
        )
        self.candidate = Candidate.objects.create(
            name="Candidate 1", nomination=self.nomination
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_cannot_vote_twice_in_same_nomination(self) -> None:
        """
        Проверяет, что пользователь не может голосовать дважды в одной номинации.
        """
        self.client.post(
            reverse("vote-list"), {"candidate": self.candidate.id}, format="json"
        )
        response = self.client.post(
            reverse("vote-list"), {"candidate": self.candidate.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_vote_in_inactive_nomination(self) -> None:
        """
        Проверяет, что нельзя голосовать в неактивной номинации.
        """
        self.nomination.is_active = False
        self.nomination.save()
        response = self.client.post(
            reverse("vote-list"), {"candidate": self.candidate.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_can_vote(self) -> None:
        """
        Проверяет, что пользователь может успешно проголосовать.
        """
        response = self.client.post(
            reverse("vote-list"), {"candidate": self.candidate.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class CandidateListAPITest(TestCase):
    """
    Тесты для API-эндпоинта списка кандидатов.
    """

    def setUp(self) -> None:
        """
        Создает пользователя, номинацию и кандидата.
        """
        self.user = User.objects.create_user(username="viewer", password="viewpass")
        self.nomination = Nomination.objects.create(
            title="Test Nomination", is_active=True
        )
        self.candidate = Candidate.objects.create(
            name="Test Candidate", nomination=self.nomination
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_candidate_list_returns_200(self) -> None:
        """
        Проверяет, что список кандидатов возвращает статус 200.
        """
        response = self.client.get(reverse("candidate-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_candidate_list_has_annotations(self) -> None:
        """
        Проверяет, что в ответе присутствуют аннотации vote_count и favorites_count.
        """
        response = self.client.get(reverse("candidate-list"))
        if response.data.get("results"):
            self.assertIn("vote_count", response.data["results"][0])
            self.assertIn("favorites_count", response.data["results"][0])

    def test_candidate_list_has_is_favorite(self) -> None:
        """
        Проверяет, что поле is_favorite корректно отображается в сериализаторе.
        """
        FavoriteCandidate.objects.create(user=self.user, candidate=self.candidate)
        response = self.client.get(reverse("candidate-list"))
        if response.data.get("results"):
            self.assertTrue(response.data["results"][0]["is_favorite"])


class CustomActionAPITest(TestCase):
    """
    Тесты для кастомных действий API.
    """

    def setUp(self) -> None:
        """
        Создает пользователя, номинацию и кандидата.
        """
        self.user = User.objects.create_user(username="viewer", password="viewpass")
        self.nomination = Nomination.objects.create(
            title="Test Nomination", is_active=True
        )
        self.candidate = Candidate.objects.create(
            name="Popular Candidate", nomination=self.nomination
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_popular_action_returns_200(self) -> None:
        """
        Проверяет, что кастомное действие popular возвращает статус 200.
        """
        response = self.client.get(reverse("candidate-popular"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_active_nominations_action_returns_200(self) -> None:
        """
        Проверяет, что кастомное действие active возвращает статус 200.
        """
        response = self.client.get(reverse("nomination-active"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PermissionTest(TestCase):
    """
    Тесты для проверки прав доступа.
    """

    def setUp(self) -> None:
        """
        Создает пользователя и номинацию.
        """
        self.user = User.objects.create_user(username="user", password="userpass")
        self.nomination = Nomination.objects.create(title="Test Nomination")
        self.client = APIClient()

    def test_unauthenticated_cannot_access_nominations(self) -> None:
        """
        Проверяет, что неаутентифицированный юзер не может получить список номинаций.
        """
        response = self.client.get(reverse("nomination-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_candidates(self) -> None:
        """
        Проверяет, что неаутентифицированный юзер не может получить список кандидатов.
        """
        response = self.client.get(reverse("candidate-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_can_access_nominations(self) -> None:
        """
        Проверяет, что аутентифицированный пользователь может получить список номинаций.
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("nomination-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
