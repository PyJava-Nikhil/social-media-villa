from celery import task
from notification.models import Notifcation
from tweet_account.models import TwitterAccount
import traceback

@task()
def create_notification(user_id, message):
    try:
        notification_obj = Notifcation.objects.create(
            user_id = user_id,
            notification = message
        )
        return True
    except Exception as e:
        traceback.print_exc()
        return False

# @task()
# def account_sync():
#     try:
#         twitter_account = TwitterAccount.objects.filter(is_active=True, is_deleted=False, access_revoked=False)
#         for i in twitter_account:
#
#     except Exception as e:
#         traceback.print_exc()
#         return False