"""
Кастомные разрешения для приложения polls.

Содержит классы разрешений для разграничения прав доступа:
    - IsAdminOrReadOnly: администратор может всё, остальные только читают
    - IsAdminUser: только для администраторов
    - IsOwnerOrAdmin: владелец объекта или администратор
"""

from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешение: администратор может выполнять любые действия,
    остальные пользователи могут только читать (GET, HEAD, OPTIONS).

    Используется для:
        - NominationViewSet
        - CandidateViewSet
    """

    def has_permission(self, request, view):
        """
        Проверяет разрешение на уровне запроса.

        Args:
            request: HTTP запрос.
            view: Представление, к которому применяется разрешение.

        Returns:
            bool: True если разрешено, иначе False.
        """
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsAdminUser(permissions.BasePermission):
    """
    Разрешение: только для администраторов.

    Используется для:
        - JuryMemberViewSet (полный доступ)
        - Управление пользователями
    """

    def has_permission(self, request, view):
        """
        Проверяет разрешение на уровне запроса.

        Args:
            request: HTTP запрос.
            view: Представление, к которому применяется разрешение.

        Returns:
            bool: True если пользователь администратор, иначе False.
        """
        return request.user and request.user.is_staff


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Разрешение: владелец объекта или администратор.

    Используется для:
        - VoteViewSet: пользователь может управлять только своими голосами
        - Администратор может управлять любыми голосами

    Проверяет, что:
        1. Пользователь является администратором (is_staff) → разрешено
        2. Пользователь является владельцем объекта (user == request.user) → разрешено
    """

    def has_object_permission(self, request, view, obj):
        """
        Проверяет разрешение на уровне объекта.

        Args:
            request: HTTP запрос.
            view: Представление, к которому применяется разрешение.
            obj: Объект, к которому применяется разрешение.

        Returns:
            bool: True если разрешено, иначе False.
        """
        if request.user and request.user.is_staff:
            return True
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "created_by"):
            return obj.created_by == request.user
        return False
