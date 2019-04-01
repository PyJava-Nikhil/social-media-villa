from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.fields import ArrayField
from django.db.models.signals import post_save
from django.dispatch import receiver
# Create your models here.

class UserAccountInfo(models.Model):
    """This model will be used to hold other info of user
    Field to be deprecated is type_use and is being moved to twitter account
    """
    USECHOICES = (
        ("SPORTS", "SPORTS"),
        ("MUSIC", "MUSIC"),
        ("ENTERTAINMENT", "ENTERTAINMENT"),
        ("LIFESTYLE", "LIFESTYLE"),
        ("GOVERNMENT&POLITICS", "GOVERNMENT&POLITICS"),
        ("BUSINESS CEO", "BUSINESS CEO"),
        ("WOMEN&NGO'S", "WOMEN&NGO'S")
    )
    INTENDCHOICE = (("B", "BUSINESS"), ("P", "PERSONAL"))
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    intended_use = models.CharField(choices=INTENDCHOICE, max_length=1, default="P")
    type_use = ArrayField(models.CharField(choices=USECHOICES, max_length=40, blank=True, null=True, default="SPORTS"), null=True, blank=True)
    choices_made = models.BooleanField(default=False)
    is_trial = models.BooleanField(default=True)
    remaining_days = models.PositiveIntegerField(default=3)
    forgot_link = models.CharField(max_length=200, null=True, blank=True)
    activation_link = models.CharField(max_length=200, null=True, blank=True)
    country_code = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.user.first_name

@receiver(post_save, sender=User)
def create_acc_info(sender, instance, created, **kwargs):
    if created:
        UserAccountInfo.objects.create(user=instance)


class TwitterAccount(models.Model):


    USECHOICES = (
        ("GENERAL", "GENERAL"),
        ("SPORTS", "SPORTS"),
        ("MUSIC", "MUSIC"),
        ("ENTERTAINMENT", "ENTERTAINMENT"),
        ("LIFESTYLE", "LIFESTYLE"),
        ("GOVERNMENT&POLITICS", "GOVERNMENT&POLITICS"),
        ("BUSINESS CEO", "BUSINESS CEO"),
        ("WOMEN&NGO'S", "WOMEN&NGO'S"),
        ("FASHION", "FASHION"),
        ("NEWS", "NEWS"),
        ("TECH", "TECH"),
        ("QUOTES", "QUOTES"),
        ("GRAPHICS DESIGNING", "GRAPHICS DESIGNING"),
        ("HEALTH", "HEALTH")
    )

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    twitter_account_detail = JSONField(default={})
    type_use = ArrayField(models.CharField(choices=USECHOICES, max_length=40, null=True, blank=True), default=[])
    access_token = models.CharField(max_length=500, null=True, blank=True)
    access_secret = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    access_revoked = models.BooleanField(default=False)
    subscription = models.BooleanField(default=False)
    suspended = models.BooleanField(default=False)
    retweet_allow = models.BooleanField(default=True, help_text="to check whether the twitter account can retweet or not")

    def __str__(self):
        return str(self.access_token) + str(self.user.email)


class TwitterUrl(models.Model):

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    url = models.CharField(max_length=500, blank=True, null=True)
    oauth_token = models.CharField(max_length=200, blank=True, null=True)
    oauth_token_secret = models.CharField(max_length=200, blank=True, null=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return self.oauth_token_secret


class TweetData(models.Model):

    USECHOICES = (
        ("GENERAL", "GENERAL"),
        ("SPORTS", "SPORTS"),
        ("MUSIC", "MUSIC"),
        ("ENTERTAINMENT", "ENTERTAINMENT"),
        ("LIFESTYLE", "LIFESTYLE"),
        ("GOVERNMENT&POLITICS", "GOVERNMENT&POLITICS"),
        ("BUSINESS CEO", "BUSINESS CEO"),
        ("WOMEN&NGO'S", "WOMEN&NGO'S"),
        ("FASHION", "FASHION"),
        ("NEWS", "NEWS"),
        ("TECH", "TECH"),
        ("QUOTES", "QUOTES"),
        ("GRAPHICS DESIGNING", "GRAPHICS DESIGNING"),
        ("HEALTH", "HEALTH")
    )

    account = models.ForeignKey(TwitterAccount, on_delete=models.CASCADE)
    url = models.URLField(null=True, blank=True)
    tweet_data = JSONField(default={})
    likes = models.BooleanField(default=False)
    like_retweet = models.BooleanField(default=False)
    date_time_submitted = models.DateTimeField(null=True, blank=True)
    date_time_verified = models.DateTimeField(null=True, blank=True)
    admin_verified = models.BooleanField(default=False)
    admin_like_count = models.PositiveIntegerField(default=0)
    admin_like_retweet_count = models.PositiveIntegerField(default=0)
    last_execution = models.DateTimeField(null=True, blank=True)
    next_execution = models.DateTimeField(null=True, blank=True)
    who_liked = ArrayField(models.IntegerField(), null=True, blank=True)
    who_liked_retweeted = ArrayField(models.IntegerField(), null=True, blank=True)
    is_active = models.BooleanField(default=False)
    in_queue = models.BooleanField(default=False)
    account_count = models.PositiveIntegerField(default=0, help_text="how many users has to be assigned to this tweet")
    tweet_category = models.CharField(choices=USECHOICES, max_length=50, null=True, blank=True)
    initial_like_user_count = models.PositiveIntegerField(default=0, help_text="use with both only like case and like retweet case where half user will like and half like retweet")
    initial_retweet_user_count = models.PositiveIntegerField(default=0, help_text="only use this in case of like_retweet due to half like and half like and retweet case")
    suspended = models.BooleanField(default=False)
    is_done = models.BooleanField(default=False)

    def __str__(self):
        return str(self.url)

class TweetUsers(models.Model):

    tweet = models.ForeignKey(TweetData, on_delete=models.CASCADE)
    twitter_account = models.OneToOneField(TwitterAccount, on_delete=models.CASCADE)
    like = models.BooleanField(default=False, help_text="use this user for liking only")
    like_retweet = models.BooleanField(default=False, help_text="use this user for both like and retweeting")
    error_liking = models.BooleanField(default=False)
    error_retweeting = models.BooleanField(default=False)

class LikeRetweetData(models.Model):
    """ This model to keep track of the error occured while liking or retweeting the tweet """
    tweet_id = models.PositiveIntegerField(default=0, help_text="this tweet id is the tweetdata object id")
    twitter_account = models.PositiveIntegerField(default=0, help_text="this is the object id of twitter account")
    like_status = JSONField(default={}, null=True, blank=True)
    retweet_status = JSONField(default={}, null=True, blank=True)