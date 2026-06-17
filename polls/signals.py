from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .tasks import send_welcome_email

User = get_user_model()


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    if created and instance.email:
        transaction.on_commit(lambda: send_welcome_email.delay(instance.id))
