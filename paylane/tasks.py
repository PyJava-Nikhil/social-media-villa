from celery import task
from paylane.models import Subscription, TransactionStatus, ContactUs
from django.conf import settings
from mailin import Mailin
from paylane.paylane_rest_client import client
from tweet_account.models import UserAccountInfo
import datetime
import traceback


@task()
def renewal():
    try:
        subscription_qs = Subscription.objects.filter(is_active=True)
        for i in subscription_qs:
            if i.renewal_date <= datetime.datetime.now():
                resale_params = {
                    'id_sale': i.sale,
                    'amount': i.pack_price,
                    'currency': i.currency,
                    'description' : "Recurring billing "+ i.pack_description
                }

                status =client.resale_by_sale(resale_params)
                TransactionStatus.objects.create(subscription=i, status=status)
                if status["success"]:
                    i.last_payment = i.renewal_date
                    i.renewal_date = i.renewal_date + datetime.timedelta(days=30)
                    i.sale = status["id_sale"]
                    i.save()
        return True
    except Exception as e:
        traceback.print_exc()
        return "error"


@task()
def trial_off(user_id):
    try:
        user_account = UserAccountInfo.objects.get(user_id=user_id)
        user_account.is_trial = False
        user_account.remaining_days = 0
        user_account.save()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

@task()
def send_query(create_id, email1, subject, content):
    try:
        contact_obj = ContactUs.objects.get(id=create_id)
        email = Mailin("https://api.sendinblue.com/v2.0", settings.MAILIN_SECRET_KEY)
        email.send_email({
            "to": {"support@socialmediavilla.com": "to Social Media Villa"},
            "from": [email1, email1],
            "subject": "Request For Pricing",
            "html": content,
            "attachment": []
        })
        #contact_obj.status = email
        #contact_obj.save()
        return email

    except Exception as e:
        traceback.print_exc()
        return str(e)
