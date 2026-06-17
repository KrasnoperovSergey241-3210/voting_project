import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


app.conf.beat_schedule = {
    "send_daily_voting_stats": {
        "task": "polls.tasks.send_daily_voting_stats",
        "schedule": crontab(hour=9, minute=0),
    },
    "auto_close_expired_nominations": {
        "task": "polls.tasks.auto_close_expired_nominations",
        "schedule": crontab(minute="*/1"),
    },
    "send_weekly_voting_report": {
        "task": "polls.tasks.send_weekly_voting_report",
        "schedule": crontab(day_of_week=0, hour=18, minute=0),
    },
}
