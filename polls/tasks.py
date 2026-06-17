from datetime import timedelta

from celery import shared_task
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.utils import timezone

from .models import Candidate, Nomination, Vote

User = get_user_model()


@shared_task
def send_welcome_email(user_id):
    try:
        user = User.objects.get(id=user_id)
        if not user.email:
            return f"User {user_id} has no email"

        send_mail(
            subject="Добро пожаловать в систему голосования!",
            message=(
                f"Здравствуйте, {user.username}!\n\n"
                f"Вы успешно зарегистрировались в системе онлайн-голосования.\n"
                f"Теперь вы можете голосовать за понравившихся кандидатов.\n\n"
                f"С уважением,\nКоманда проекта"
            ),
            from_email="noreply@voting-app.com",
            recipient_list=[user.email],
            fail_silently=False,
        )
        return f"Welcome email sent to {user.email}"
    except User.DoesNotExist:
        return f"User {user_id} not found"


@shared_task
def send_daily_voting_stats():
    admins = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

    if not admins.exists():
        return "No admins found to send stats"

    total_nominations = Nomination.objects.count()
    active_nominations = Nomination.objects.filter(is_active=True).count()
    total_candidates = Candidate.objects.count()
    total_votes = Vote.objects.count()

    nominations_stats = []
    for nomination in Nomination.objects.filter(is_active=True).annotate(
        candidate_count=Count("candidates", distinct=True),
        vote_count=Count("candidates__votes", distinct=True),
    ):
        nominations_stats.append(
            f"  * {nomination.title}: {nomination.vote_count} голосов, "
            f"{nomination.candidate_count} кандидатов"
        )

    top_candidates = Candidate.objects.annotate(vote_count=Count("votes")).order_by(
        "-vote_count"
    )[:5]

    top_candidates_text = []
    for idx, candidate in enumerate(top_candidates, 1):
        top_candidates_text.append(
            f"  {idx}. {candidate.name} ({candidate.nomination.title}) — "
            f"{candidate.vote_count} голосов"
        )

    subject = f"Статистика голосования за {timezone.now().date()}"

    message = f"""
Здравствуйте, администратор!

Ежедневный отчет по системе голосования.

Общая статистика:
Всего номинаций: {total_nominations}
Активных номинаций: {active_nominations}
Всего кандидатов: {total_candidates}
Всего голосов: {total_votes}

Активные номинации:
{chr(10).join(nominations_stats) if nominations_stats else "  Нет активных номинаций"}

Топ-5 кандидатов по голосам:
{chr(10).join(top_candidates_text) if top_candidates_text else "  Нет голосов"}

Отчет сгенерирован: {timezone.now().strftime("%d.%m.%Y %H:%M")}

С уважением,
Система онлайн-голосования
"""

    admin_emails = [admin.email for admin in admins if admin.email]

    if not admin_emails:
        return "No admin emails found"

    send_mail(
        subject=subject,
        message=message,
        from_email="noreply@voting-app.com",
        recipient_list=admin_emails,
        fail_silently=False,
    )

    return f"Daily stats sent to {len(admin_emails)} admins"


@shared_task
def auto_close_expired_nominations():
    expiration_days = 30
    expiration_date = timezone.now() - timedelta(days=expiration_days)

    expired_nominations = Nomination.objects.filter(
        is_active=True, created_at__lte=expiration_date
    )

    if not expired_nominations.exists():
        return f"No expired nominations found (threshold: {expiration_days} days)"

    count = expired_nominations.count()

    for nomination in expired_nominations:
        nomination.is_active = False
        nomination.save()

        LogEntry.objects.log_action(
            user_id=1,
            content_type_id=ContentType.objects.get_for_model(nomination).id,
            object_id=nomination.id,
            object_repr=str(nomination),
            action_flag=2,
            change_message=f"Автоматически закрыта (истек срок {expiration_days} дней)",
        )

    admins = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
    admin_emails = [admin.email for admin in admins if admin.email]

    if admin_emails:
        nominations_list = "\n".join([f"  * {n.title}" for n in expired_nominations])

        send_mail(
            subject=f"Автоматически закрыты номинации ({count})",
            message=f"""
Здравствуйте, администратор!

Автоматически закрыты следующие номинации
(истек срок голосования {expiration_days} дней):

{nominations_list}

Всего закрыто: {count} номинаций.

С уважением,
Система онлайн-голосования
""",
            from_email="noreply@voting-app.com",
            recipient_list=admin_emails,
            fail_silently=False,
        )

    return f"Closed {count} expired nominations"


@shared_task
def send_weekly_voting_report():
    week_ago = timezone.now() - timedelta(days=7)

    new_votes = Vote.objects.filter(created_at__gte=week_ago).count()
    new_users = User.objects.filter(date_joined__gte=week_ago).count()
    new_nominations = Nomination.objects.filter(created_at__gte=week_ago).count()
    new_candidates = Candidate.objects.filter(created_at__gte=week_ago).count()

    nominations_stats = (
        Nomination.objects.filter(is_active=True)
        .annotate(
            candidate_count=Count("candidates", distinct=True),
            vote_count=Count("candidates__votes", distinct=True),
        )
        .order_by("-vote_count")[:10]
    )

    nominations_text = []
    for nom in nominations_stats:
        nominations_text.append(
            f"  * {nom.title}: {nom.vote_count} голосов, "
            f"{nom.candidate_count} кандидатов"
        )

    admins = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
    admin_emails = [admin.email for admin in admins if admin.email]

    if not admin_emails:
        return "No admin emails found"

    subject = f"Еженедельный отчет по голосованию ({timezone.now().date()})"

    message = f"""
Здравствуйте, администратор!

Еженедельный отчет по системе голосования.

Активность за неделю (с {week_ago.strftime("%d.%m.%Y")}):
Новых голосов: {new_votes}
Новых пользователей: {new_users}
Новых номинаций: {new_nominations}
Новых кандидатов: {new_candidates}

Топ-10 активных номинаций:
{chr(10).join(nominations_text) if nominations_text else "  Нет активных номинаций"}

Отчет сгенерирован: {timezone.now().strftime("%d.%m.%Y %H:%M")}

С уважением,
Система онлайн-голосования
"""

    send_mail(
        subject=subject,
        message=message,
        from_email="noreply@voting-app.com",
        recipient_list=admin_emails,
        fail_silently=False,
    )

    return f"Weekly report sent to {len(admin_emails)} admins"
