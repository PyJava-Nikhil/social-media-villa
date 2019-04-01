from celery import shared_task, task
from tweet_account.models import TwitterAccount, TweetData, TweetUsers, UserAccountInfo, LikeRetweetData
from twython import Twython
import twython
from django.conf import settings
from mailin import Mailin
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from oauth2_provider.models import AccessToken, Application
from notification.tasks import create_notification
import datetime
import traceback
import requests
import random, string
import time


consumer_key = settings.CONSUMER_KEY
consumer_secret = settings.CONSUMER_SECRET

@shared_task
def get_user_detail(token, secret):
    try:
        api = Twython(consumer_key, consumer_secret, token, secret)
        screen_name = api.get_account_settings()["screen_name"]
        followers_count = api.get_followers_list()["users"]
        image_url = requests.get(url="https://twitter.com/"+screen_name+"/profile_image?size=original").url
        twitter_account_obj = TwitterAccount.objects.get(access_token=token, access_secret=secret)
        save_json = {
            "screen_name":screen_name,
            "followers_count":len(followers_count),
            "image_url":image_url
        }
        twitter_account_obj.twitter_account_detail = save_json
        twitter_account_obj.save()
        return True
    except Exception as e:
        return str(e)

@shared_task
def create_tweet_data(obj, tweet, submission_date, link):
    try:
        tweet_data_obj = TweetData.objects.create(
            account=obj,
            tweet_data = tweet,
            date_time_submitted = submission_date,
            url = link
        )
        return tweet_data_obj.id
    except Exception as e:
        traceback.print_exc()
        return 0

def random_time_generator(current_time):
    next_execution_time = current_time + datetime.timedelta(
        hours=random.randrange(0, 4),
        minutes=random.randrange(0, 25),
        seconds=random.randrange(0, 30)
    )
    return next_execution_time

@task()
def assign_tweet_users(tweet_id, user_id):
    """ To link users with one particular tweet to like or like + retweet it.
        % of account to be used to select from portion of accounts.
    """
    try:

        tweet_data_obj = TweetData.objects.get(id=tweet_id)
        account_qs = [x.id for x in TwitterAccount.objects.filter(is_active=True, access_revoked=False).exclude(user_id=user_id)]
        in_use = [x.twitter_account.id for x in TweetUsers.objects.all()]
        admin_set_percent = tweet_data_obj.admin_like_count + tweet_data_obj.admin_like_retweet_count # will be set by admin

        not_used = list(set(account_qs) - set(in_use))
        accounts_to_be_used = admin_set_percent
        print(not_used)
        if len(not_used) <= accounts_to_be_used:
            to_be_assigned = not_used
            print("eith if")
        elif len(not_used) > accounts_to_be_used:
            to_be_assigned = random.sample(set(not_used), accounts_to_be_used)
            print("with_elif")

        else:
            to_be_assigned = []

        like_retweet_count = 0
        like_count = 0
        print("to_bes", to_be_assigned)
        if len(to_be_assigned)!=0:

            for i in to_be_assigned:
                print(i,">>>>>>>>>>>>>>>>>>>>")
                user = TwitterAccount.objects.get(id=i).user

                if tweet_data_obj.likes and not tweet_data_obj.like_retweet:

                    tweet_users = TweetUsers.objects.create(
                        tweet_id=tweet_id,
                        twitter_account_id=i,
                        like=True,
                        like_retweet=False)
                    like_count = like_count +1

                else:
                    # user_choice = UserAccountInfo.objects.get(user=user).type_use
                    twitter_obj = TwitterAccount.objects.get(id=i)
                    if twitter_obj.retweet_allow:
                        if tweet_data_obj.tweet_category in twitter_obj.type_use or "GENERAL" in twitter_obj.type_use :
                            if TweetUsers.objects.filter(like_retweet=True, like=False, tweet_id=tweet_id).count() < tweet_data_obj.admin_like_retweet_count:
                                tweet_users = TweetUsers.objects.create(
                                    tweet_id=tweet_id,
                                    twitter_account_id=i,
                                    like=False,
                                    like_retweet=True
                                )
                                like_retweet_count = like_retweet_count + 1
                            else:
                                print(like_count, "like_count bhgshgdh")
                                if TweetUsers.objects.filter(like=True,tweet_id=tweet_id).count() < tweet_data_obj.admin_like_count:
                                    tweet_users = TweetUsers.objects.create(
                                        tweet_id=tweet_id,
                                        twitter_account_id=i,
                                        like=True,
                                        like_retweet=False)
                                    like_count = like_count + 1
                                    print("while retweeting and liking but quota is full in case of retweeting so assigning like users")
                        else:
                            print("like only >>>>>>>>>>")
                            if TweetUsers.objects.filter(like=True, tweet_id=tweet_id).count() < tweet_data_obj.admin_like_count:
                                tweet_users = TweetUsers.objects.create(
                                    tweet_id=tweet_id,
                                    twitter_account_id=i,
                                    like=True,
                                    like_retweet=False)
                                print("creation in process")
                                like_count = like_count + 1
                    else:
                        if TweetUsers.objects.filter(like=True,
                                                     tweet_id=tweet_id).count() < tweet_data_obj.admin_like_count:
                            tweet_users = TweetUsers.objects.create(
                                tweet_id=tweet_id,
                                twitter_account_id=i,
                                like=True,
                                like_retweet=False)
                            print("creation in process")
                            like_count = like_count + 1

            tweet_data_obj.in_queue = True
            tweet_data_obj.save()

        current_time = datetime.datetime.now()
        next_execution_time = random_time_generator(current_time)
        print(like_count, ">>>>>>>>>>>>>", like_retweet_count)
        tweet_data_obj.is_active = True
        tweet_data_obj.admin_verified = True
        tweet_data_obj.account_count = accounts_to_be_used
        tweet_data_obj.initial_like_user_count = like_count
        tweet_data_obj.initial_retweet_user_count = like_retweet_count
        tweet_data_obj.next_execution = next_execution_time
        tweet_data_obj.save()

        return True

    except Exception as e:

        traceback.print_exc()
        return str(e)


def revoked_access(account_id):

    twitter_account_obj = TwitterAccount.objects.get(id=account_id,is_active=True, is_deleted=False, access_revoked=False)
    api = Twython(consumer_key, consumer_secret, twitter_account_obj.access_token, twitter_account_obj.access_secret)
    try:
        api.get_account_settings()
        return True
    except twython.TwythonAuthError as e:
        twitter_account_obj.access_revoked = True
        twitter_account_obj.is_active = False
        twitter_account_obj.save()
        traceback.print_exc()
        return str(e)



def api_favourite_task(twython_object, tweet_id):
    favourite_api = twython_object
    try:
        status = favourite_api.create_favorite(id=tweet_id)
        return status
    except twython.TwythonError as e:
        error = {"error": str(e)}
        return error

@task()
def like_retweet():
    try:
        current_time = datetime.datetime.now()
        tweet_ids = [x.id for x in TweetData.objects.filter(
        is_active=True,
        admin_verified=True,
        in_queue=True,
        next_execution__lte=current_time)
        ]
        print(current_time, "current time>>>>>>>>>>>>>>>>>>>")
        if len(tweet_ids)!=0:
            random_tweet = TweetData.objects.get(id=random.choice(tweet_ids))
            tweet_user_qs = TweetUsers.objects.filter(tweet=random_tweet, error_liking=False, error_retweeting=False)

            if tweet_user_qs.exists():

                random_choice = random.randrange(len(tweet_user_qs))
                tweet_user_obj = tweet_user_qs[random_choice]

                twitter_account_obj = TwitterAccount.objects.get(id=tweet_user_obj.twitter_account_id, access_revoked=False)
                revoke_or_not = revoked_access(twitter_account_obj.id)
                print(revoke_or_not, ">>>>>>>>>>>>>>>")
                if not revoke_or_not:
                    return "access is revoked for this account"
                access_token = twitter_account_obj.access_token
                access_secret = twitter_account_obj.access_secret

                favourite_api = Twython(consumer_key, consumer_secret, access_token, access_secret)

                if tweet_user_obj.like:

                    status = api_favourite_task(favourite_api, random_tweet.tweet_data["id"])
                    print(status, "in liking >>>>>>>>>>>>>>")
                    data_obj = LikeRetweetData.objects.create(
                        tweet_id=random_tweet.id,
                        twitter_account=twitter_account_obj.id,
                        like_status=status)

                    if data_obj.like_status.get("error"):
                        tweet_user_obj.error_liking = True
                        tweet_user_obj.save()


                    else:
                        who_liked = random_tweet.who_liked
                        if who_liked == None:
                            who_liked = []
                        who_liked.append(twitter_account_obj.id)
                        random_tweet.who_liked = who_liked
                        random_tweet.last_execution = random_tweet.next_execution
                        current_time = datetime.datetime.now()
                        random_tweet.next_execution = random_time_generator(current_time)
                        random_tweet.save()
                        tweet_user_obj.delete()
                        message = "Your tweet(<font color='black'> url-" + random_tweet.url + "</font>) linked with twitter account @<font color='black'>" + \
                                  random_tweet.account.twitter_account_detail["screen_name"] + "</font> is liked by <font color='black'>Social Media Villa</font> on "+ \
                                    datetime.datetime.strftime(random_tweet.last_execution, "%Y-%m-%d on %I:%M %p")
                        create_notification.delay(random_tweet.account.user_id, message)

                else:

                    status = api_favourite_task(favourite_api, random_tweet.tweet_data["id"])
                    print(status, "while liking in retweeting")
                    random_seconds = random.randrange(5, 14)
                    time.sleep(random_seconds)
                    try:

                        retweet_status = favourite_api.retweet(id=random_tweet.tweet_data["id"])
                        print(retweet_status, "in retweeting >>>>>>>>")
                    except twython.TwythonError as e:
                        retweet_status = {"error":str(e)}

                    data_obj = LikeRetweetData.objects.create(
                        tweet_id=random_tweet.id,
                        twitter_account=twitter_account_obj.id,
                        retweet_status=retweet_status,
                        like_status=status
                        )
                    final_status = False

                    if data_obj.like_status.get("error"):
                        tweet_user_obj.error_liking = True
                        final_status = True
                        tweet_user_obj.save()

                    if data_obj.retweet_status.get("error"):
                        tweet_user_obj.error_retweeting = True
                        final_status = True
                        tweet_user_obj.save()


                    if not final_status:
                        who_retweeted = random_tweet.who_liked_retweeted
                        if who_retweeted == None:
                            who_retweeted = []
                        who_retweeted.append(twitter_account_obj.id)
                        random_tweet.who_liked_retweeted = who_retweeted
                        random_tweet.last_execution = random_tweet.next_execution
                        current_time = datetime.datetime.now()
                        random_tweet.next_execution = random_time_generator(current_time)
                        random_tweet.save()
                        tweet_user_obj.delete()
                        message = "Your tweet(<font color='black'> url-" + random_tweet.url + "</font>) linked with twitter account @<font color='black'>" + \
                                  random_tweet.account.twitter_account_detail[
                                      "screen_name"] + "</font> is liked and retweeted by <font color='black'>Social Media Villa</font> on " + \
                                  datetime.datetime.strftime(random_tweet.last_execution, "%Y-%m-%d on %I:%M %p")
                        create_notification(random_tweet.account.user_id, message)
        else:
            return "Nothing to do"
        return True
    except Exception as e:
        traceback.print_exc()
        return str(e)



@task()
def deactivate_in_queue():
    """ To remove the tweets from active queues when the quota is completed"""
    try:

        tweet_qs = TweetData.objects.filter(is_active=True, in_queue=True)
        for i in tweet_qs:
            if i.likes and not i.like_retweet:
                who_liked = i.who_liked
                if not who_liked:
                    who_liked = []
                if len(i.who_liked) == i.account_count:
                    i.is_active = False
                    i.in_queue = False
                    i.is_done = True
                    i.save()
            else:
                who_liked = i.who_liked
                who_liked_retweeted = i.who_liked_retweeted
                if not who_liked:
                    who_liked = []
                if not who_liked_retweeted:
                    who_liked_retweeted = []
                if (len(who_liked) + len(who_liked_retweeted)) == i.account_count:
                    i.is_active = False
                    i.in_queue = False
                    i.is_done = True
                    i.save()
        return True
    except Exception as e:
        traceback.print_exc()
        return str(e)


def html_to_string(body, user_email, type):
    user = User.objects.get(email=user_email)
    user_account_info = UserAccountInfo.objects.get(user=user)
    app = Application.objects.get(user=user)

    if type=="f":
        user_cipher = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(15))
        key_cipher = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20))
        rendered = render_to_string(body, {"user_cipher":user_cipher, "key_cipher":key_cipher})
        AccessToken.objects.create(
            token=key_cipher,
            expires=datetime.datetime.now()+ datetime.timedelta(minutes=30),
            application=app,
            user=user,
            scope="read write"
        )
        user_account_info.forgot_link = "https://smv.sia.co.in/api/account/v1/forgot_password_verify/?ab="+user_cipher+"&ac="+key_cipher
        user_account_info.save()

    elif type == "a":
        user_cipher = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(15))
        rendered = render_to_string(body, {"cipher": user_cipher})
        user_account_info.activation_link = "https://smv.sia.co.in/api/account/v1/activate/?user="+user_cipher
        user_account_info.save()

    else:
        pass

    return rendered

@task()
def send_email(email_type, user_email):
    try:
        if email_type=="f":
            subject = "Reset Password Link"
            body = 'tweet_account/forgot_password.html'
            string_content = html_to_string(body, user_email, "f")

        elif email_type =="a":

            subject = "Verify Your Email"
            body = 'tweet_account/activation_email.html'
            string_content = html_to_string(body, user_email, "a")

        elif email_type =="w":

            subject = "Welcome To Social Media Villa"
            body = 'tweet_account/welcome_email.html'
            string_content = html_to_string(body, user_email, "w")

        else:
            return False

        email = Mailin("https://api.sendinblue.com/v2.0", settings.MAILIN_SECRET_KEY)
        email.send_email({
            "to": {user_email: "to "+user_email},
            "from": ["support@socialmediavilla.com", "Social Media Villa"],
            "subject": subject,
            "html": string_content,
            "attachment": []
        })
        return email
    except Exception as e:
        traceback.print_exc()
        return False

@task()
def trial_end():
    try:
        user_qs = UserAccountInfo.objects.filter(user__is_active=True, is_trial=True)
        for i in user_qs:
            if i.remaining_days !=0:
                i.remaining_days = i.remaining_days - 1
                i.save()
                if i.remaining_days ==0:
                    i.is_trial = False
                i.save()
            else:
                i.is_trial = False
                i.save()
    except Exception as e:
        traceback.print_exc()
        return False


@task()
def pending_assign():
    """ This task assigns the tweet its pending likers or retweeters"""
    try:
        tweet_qs = TweetData.objects.filter(is_active=True, in_queue=True)
        tweet_users = [x.twitter_account_id for x in TweetUsers.objects.all()]
        for i in tweet_qs:
            if i.likes and not i.like_retweet:

                if i.initial_like_user_count == 0:
                    assign_tweet_users(i.id, i.account.user_id)

                elif i.initial_like_user_count < i.admin_like_count:

                    already_liked = i.who_liked
                    not_use = tweet_users + already_liked#this is the list of twitter accounts not to be used for liking the tweet

                    to_be_used = [x.id for x in TwitterAccount.objects.filter(
                        is_active=True,
                        access_revoked=False).exclude(id__in=not_use)
                    ]

                    like_count = 0
                    for assign in to_be_used:
                        if TweetUsers.objects.filter(tweet_id=i.id, ).count() < i.admin_like_count :
                            TweetUsers.objects.create(
                                tweet_id = i.id,
                                twitter_account_id = assign,
                                like = True,
                                like_retweet = False
                            )
                            like_count+= 1
                    i.initial_like_user_count = i.initial_like_user_count + like_count
                    i.save()

                else:
                    pass
            else:
                if (i.initial_like_user_count + i.initial_retweet_user_count) == 0:
                    assign_tweet_users(i.id, i.account.user_id)

                if i.initial_like_user_count < i.admin_like_count:

                    already_liked = i.who_liked
                    if not already_liked:
                        already_liked = []
                    not_use = tweet_users + already_liked
                    to_be_used = [x.id for x in TwitterAccount.objects.filter(
                        is_active=True,
                        access_revoked=False).exclude(id__in=not_use)
                    ]
                    like_count = 0
                    for r_like in to_be_used:
                        if TweetUsers.objects.filter(tweet_id=i.id, like=True).count() < i.admin_like_count:
                            TweetUsers.objects.create(
                                tweet_id=i.id,
                                twitter_account_id = r_like,
                                like=True,
                                like_retweet = False
                            )

                            like_count +=1
                    i.initial_like_user_count = i.initial_like_user_count + like_count
                    i.save()

                if i.initial_retweet_user_count < i.admin_like_retweet_count:
                    already_retweeted = i.who_liked_retweeted
                    if not already_retweeted:
                        already_retweeted = []
                    print(str(i.account_id)+"printing twitter account id ",type([x.twitter_account_id for x in TweetUsers.objects.all()]), type(already_retweeted))
                    not_use = [x.twitter_account_id for x in TweetUsers.objects.all()] + already_retweeted + [i.account_id]
                    to_be_used = [x.id for x in TwitterAccount.objects.filter(
                        is_active=True,
                        access_revoked=False,
                        retweet_allow=True
                    ).exclude(id__in=not_use)
                    if i.tweet_category in x.type_use or "GENERAL" in x.type_use]
                    like_retweet_count = 0
                    for re_like in to_be_used:
                        if TweetUsers.objects.filter(tweet_id=i.id, like_retweet = True).count() < i.admin_like_retweet_count:
                            TweetUsers.objects.create(
                                tweet_id = i.id,
                                twitter_account_id = re_like,
                                like_retweet = True,
                                like = False
                            )
                            like_retweet_count += 1
                    i.initial_retweet_user_count = i.initial_retweet_user_count + like_retweet_count
                    i.save()
        return True

    except Exception as e:
        traceback.print_exc()
        return str(e)
