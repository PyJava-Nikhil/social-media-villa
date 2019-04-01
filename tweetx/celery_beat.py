from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'like_retweet': {
        'task': 'tweet_account.tasks.like_retweet',
        'schedule': crontab(minute='*/1')
    },
    'deactivate_in_queue':{
        'task':'tweet_account.tasks.deactivate_in_queue',
        'schedule': crontab(minute='*/2')
    },
    'trial_end':{ #time is according to utc
        'task':'tweet_account.tasks.trial_end',
        'schedule':crontab(minute=30, hour=18)
    },

    "recurring_payment":{
        "task": "paylane.tasks.renewal",
        'schedule': crontab(minute='*/15')
    },

    "assign_pending":{
        "task": "tweet_account.tasks.pending_assign",
        "schedule": crontab(minute='*/1')
    }
}
