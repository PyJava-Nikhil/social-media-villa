from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# from
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tweetx.settings')
app = Celery('tweetx', include=["tweet_account.tasks"])

app.config_from_object('django.conf:settings', namespace="CELERY")
app.conf.broker_url = 'redis://localhost:6379/0'
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))