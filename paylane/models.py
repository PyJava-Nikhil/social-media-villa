from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField, ArrayField
from tweet_account.models import TwitterAccount
# Create your models here.


class Subscription(models.Model):


    twitter_account = models.PositiveIntegerField(default=0)
    twitter_account_detail = JSONField()
    subscription_bought = models.DateTimeField(null=True, blank=True)
    last_payment = models.DateTimeField(null=True, blank=True)
    renewal_date = models.DateTimeField(null=True, blank=True)
    payment_date_time = ArrayField(models.DateTimeField(null=True, blank=True), null=True)
    currency = models.CharField(max_length=10, null=True, blank=True)
    pack_description = models.CharField(max_length=500, null=True, blank=True)
    pack_price = models.FloatField(default=0.0)
    p_account = models.PositiveIntegerField(default=0)
    sale = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=False)


class TransactionStatus(models.Model):
    """
    This model will be used if any payment fails while renewing the subscription for a twitter account
    """
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    status = JSONField(null=True, blank=True)


class ContactUs(models.Model):

    email = models.EmailField(null=True, blank=True)
    mobile = models.CharField(max_length=20, null=True, blank=True)
    subject = models.CharField(max_length=500, null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    status = JSONField(default={"value" : None})

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return str(self.email) + " " + str(self.mobile)