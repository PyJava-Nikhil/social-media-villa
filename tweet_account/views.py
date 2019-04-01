from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from .models import TwitterAccount, TwitterUrl, TweetData, UserAccountInfo
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.contrib.auth import authenticate
from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope
from oauth2_provider.models import Application, AccessToken
from oauthlib.common import generate_token
import tweepy
from twython import Twython
from .tasks import get_user_detail,assign_tweet_users, send_email
from paylane.models import Subscription
from django.conf import settings
from django.http import HttpResponseRedirect
import traceback
import datetime
from notification.tasks import create_notification
# Create your views here.

consumer_key = settings.CONSUMER_KEY
consumer_secret = settings.CONSUMER_SECRET


def isValidEmail(email):
    """ to check the syntax of an email using django validate email"""
    try:
        validate_email(email)
        return True
    except Exception as e:
        traceback.print_exc()
        return False


class SignUp(APIView):

    """METHOD POST: Creating a new user if email and mobile is unique."""
    def post(self, request):
        try:
            data = request.data
            first_name = data["first_name"]
            last_name = data["last_name"]
            email = data["email"]
            password = data["password"]
            mobile = data["mobile"]
            mobile_component = mobile.split(" ")
            intended_use = data["intended_use"]
            if intended_use.upper() != "P" and intended_use.upper() != "B":
                intended_use = "P"
            if not mobile_component[1].isdigit():
                return Response({"error":"Invalid mobile number", "success":False}, status=400)
            try:
                user = User.objects.get(email=email.strip())
                if User.objects.filter(username=mobile).exists():
                    return Response({"mobile_exists":True, "success":False}, status=400)
                return Response({"email_exists":True, "success":False}, status=400)

            except Exception as e:

                valid = isValidEmail(email.strip())
                if valid:
                    user = User.objects.create(username=mobile_component[1], email=email.strip(), is_active=False, first_name=first_name.strip(), last_name=last_name)
                    user.set_password(password)
                    user.save()
                    app = Application.objects.create(
                        user=user, client_type=Application.CLIENT_CONFIDENTIAL,
                        authorization_grant_type=Application.GRANT_PASSWORD, 
                        name=email
                    )
                    user_account_info = UserAccountInfo.objects.get(user=user)
                    user_account_info.intended_use = intended_use
                    user_account_info.country_code = mobile_component[0]
                    user_account_info.save()
                    send_email.delay("a", user.email)
                    return Response({"user_id":user.id,
                                     "client_secret":app.client_secret,
                                     "client_id":app.client_id,
                                     "first_name":user.first_name,
                                     "last_name":user.last_name}, status=200)
                else:
                    return Response({"error":str(email)+" email format not right", "success":False}, status=400)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e)}, status=400)


class Login(APIView):

    """METHOD POST: For logging in the user and providing access token to work with other api's"""
    def post(self, request):
        try:
            data = request.data
            email = data["email"]
            password = data["password"]
            user_mobile = User.objects.get(email=email)
            if not user_mobile.is_active:
                return Response({"error" : "Please verify your email first. Check your inbox for Social Media Villa verification email."}, status=400)
            user = authenticate(username=user_mobile.username, password=password)
            if user:
                user_info = UserAccountInfo.objects.get(user=user)
                tweet_type = False
                account_exists = False
                if user_info.type_use !=None:

                    tweet_type = True

                if TwitterAccount.objects.filter(user=user, is_deleted=False).exists():
                    account_exists = True

                app = Application.objects.get(user=user)
                token = generate_token()
                token_obj = AccessToken.objects.create(
                    token = token,
                    application = app,
                    user = user,
                    scope = "read write",
                    expires = timezone.now() + timedelta(days=365)
                )
                return Response({
                    "token":token_obj.token,
                    "scope":token_obj.scope,
                    "expires":token_obj.expires,
                    "type":"bearer",
                    "client_id":app.client_id,
                    "client_secret":app.client_secret,
                    "first_name":token_obj.user.first_name,
                    "last_name":token_obj.user.last_name,
                    "tweet_type":tweet_type,
                    "email": email,
                    "mobile": user_mobile.username,
                    "account_exists":account_exists
                    }, status=200)
            else:
                return Response({"error":"Invalid user"},status=400)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e)}, status=400)


class MobileEmailCheck(APIView):
    """To check whether the mobile or email exists with other accounts"""
    def get(self, request):
        try:
            query = request.GET["query"]
            query_parameter = request.GET["parameter"]
            user = User.objects.all()
            if query.lower() == "m":
                if query_parameter.isdigit():
                    if user.filter(username=query_parameter).exists():
                        return Response({"mobile_exist":True, "message":"mobile is already linked with another account"}, status=400)
                    else:
                        return Response({"mobile_exsit":False, "message":"mobile number can be used"}, status=200)
                else:
                    return Response({"error":"Invalid query parameter"}, status=400)

            elif query.lower() == "e":
                if isValidEmail(query_parameter):

                    if user.filter(email=query_parameter).exists():
                        return Response({"email_exist":True, "message":"email exists with other account"}, status=400)
                    else:
                        return Response({"email_exist":False, "message":"email can be used"}, status=200)

                else:
                    return Response({"error":"Invalid query parameter"}, status=400)

            else:
                return Response({"error":"Invalid query parameter"}, status=400)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class ForgotPassword(APIView):
    """ This api is used to send an email with a link to let the user reset password within 30 minutes """
    def post(self, request):
        try:
            data = request.data
            email = data["email"]
            if isValidEmail(email):
                user = User.objects.get(email=email)
                send_email.delay("f", email)
                return Response({
                    "success":True,
                    "email":user.email,
                    "user_id":user.id,
                    "is_active":user.is_active
                }, status=200)

            else:
                return Response({"error":"Invalid email format", "success":False}, status=400)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class VerifyForgot(APIView):
    """ To verify the forgot link and check whether to let the user reset the password based on token expiry time"""
    def get(self, request):
        try:
            key_cipher = request.GET["ac"]
            ab = request.GET["ab"]
            user_account_info = UserAccountInfo.objects.get(forgot_link="https://smv.sia.co.in/api/account/v1/forgot_password_verify/?ab="+str(ab)+"&ac="+str(key_cipher))
            access_token =  AccessToken.objects.get(token=key_cipher)
            if access_token.expires >= datetime.datetime.now():
                return HttpResponseRedirect("https://socialmedia.sia.co.in/Resetpassword?ab="+str(ab)+"&ac="+str(key_cipher))
            else:
                return render(request, 'tweet_account/Expired.html', context={})
        except Exception as e:
            traceback.print_exc()
            return render(request, 'tweet_account/error_page.html', context={})


class Activation(APIView):
    """To activate the user account using a non expiring link to smv"""
    def get(self, request):
        try:
            key = request.GET["user"]
            print(key, ">>>>>>>>>>>>>>>>>>>>>")
            user_account_info = UserAccountInfo.objects.get(activation_link="https://smv.sia.co.in/api/account/v1/activate/?user="+key)
            user = User.objects.get(id=user_account_info.user_id)
            user.is_active = True
            user.save()

            user_account_info.activation_link = ''
            user_account_info.save()

            return HttpResponseRedirect("https://socialmedia.sia.co.in/Signin?param="+key)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class ChangePassword(APIView):
    """This api is to let the user changes his/her password"""
    permission_classes = [TokenHasReadWriteScope]

    def post(self, request):
        user = request.user
        try:
            data = request.data
            old_password = data["old_password"]
            new_password = data["new_password"]
            user_obj = User.objects.get(id=user.id, is_active=True)

            if user_obj.check_password(old_password):
                user_obj.set_password(new_password)
                user_obj.save()
                return Response({"success":True}, status=200)

            else:
                return Response({"error":"old password do not match", "success":False}, status=400)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)

    def get(self, request):
        user = request.user
        try:
            user = User.objects.get(id=user.id)
            password = request.GET["password"]
            user.set_password(password)
            user.save()
            return Response({"success":True}, status=200)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e)}, status=400)

def index(request):
    try:
        oauth_verifier = request.GET.get("oauth_verifier")
        oauth_token = request.GET.get("oauth_token")
        twitter_url_obj = TwitterUrl.objects.get(oauth_token=oauth_token)
        oauth_secret = twitter_url_obj.oauth_token_secret

        auth = Twython(consumer_key, consumer_secret, oauth_token, oauth_secret)
        token_get = auth.get_authorized_tokens(oauth_verifier)
        access_token = token_get["oauth_token"]
        access_secret = token_get["oauth_token_secret"]
        twitter_url_obj.is_used = True
        twitter_url_obj.save()

        api = Twython(consumer_key, consumer_secret, access_token, access_secret)
        screen_name = api.get_account_settings()["screen_name"]
        try:
            twitter_obj_re = TwitterAccount.objects.filter(twitter_account_detail__screen_name=screen_name, is_deleted=True, is_active=False)
            if twitter_obj_re.exists():
                twitter_obj_re = twitter_obj_re[0]
                twitter_obj_re.is_deleted = False
                twitter_obj_re.save()
                return render(request, "tweet_account/new.html", context={})
            twitter_obj = TwitterAccount.objects.get(access_token=access_token, access_secret=access_secret, is_deleted=False)
            return render(request, "tweet_account/exists.html", context={"access_token": twitter_obj.access_token, "access_secret": twitter_obj.access_secret})

        except Exception as e:
            traceback.print_exc()

        twitter_obj = TwitterAccount.objects.create(user=twitter_url_obj.user ,access_token=access_token, access_secret=access_secret)
        
        get_user_detail.delay(twitter_obj.access_token, twitter_obj.access_secret)
        return render(request, "tweet_account/new.html",context={"access_token":twitter_obj.access_token, "access_secret":twitter_obj.access_secret})

    except Exception as e:
        traceback.print_exc()
        return render(request, "tweet_account/new.html", context={"access_token": None, "access_secret": None})


class AddTwitterAccount(APIView):

    """ METHOD POST: To give the logged in user unique twitter url and get authorized with our twiter app.
        METHOD GET: To get all the twitter accounts associated with logged in user.
    """

    permission_classes = [TokenHasReadWriteScope]
    def post(self, request):
        user = request.user
        try:
            auth = Twython(consumer_key, consumer_secret)
            redirect_url = auth.get_authentication_tokens(callback_url="https://smv.sia.co.in/api/account/v1/")
            oauth_token = redirect_url["oauth_token"]
            oauth_secret = redirect_url["oauth_token_secret"]
            twitter_url_obj = TwitterUrl.objects.create(url=redirect_url, oauth_token=oauth_token, oauth_token_secret=oauth_secret, user=user)
            
            return Response({"url":redirect_url,
                             "oauth_token":oauth_token,
                             "oauth_secret":oauth_secret,
                             "id":twitter_url_obj.id}, status=200)
            
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e)}, status=400)

    def get(self, request):
        user = request.user
        try:
            twitter_account_qs = TwitterAccount.objects.filter(user=user, is_deleted=False)
            response = []
            for x in twitter_account_qs:
                if x.type_use:
                    choices = True
                    choice_category = x.type_use
                else:
                    choices = False
                    choice_category = []
                response.append({
                    "is_active" : x.is_active,
                    "user_info" : x.twitter_account_detail,
                    "suspended": x.suspended,
                    "id":x.id,
                    "choices" : choices,
                    "choice_category" : choice_category
                })
            return Response({"success":True,"data":response}, status=200)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)

    def delete(self, request, format=None):
        user = request.user
        try:
            i_d = request.GET["id"]
            if i_d.isdigit():
                twitter_account_obj = TwitterAccount.objects.get(user=user ,id=int(i_d), is_deleted=False)
                twitter_account_obj.is_deleted = True
                twitter_account_obj.is_active = False
                twitter_account_obj.save()
                return Response({"success":True}, status=200)
            else:
                return Response({"success":False, "error":"Invalid value"}, status=400)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class SubmitTweet(APIView):

    """ METHOD POST: To submit a tweet from one twitter account with validation like tweet belongs to the
                     same twitter account.

        METHOD GET: To get all the tweets submitted with one twitter account
    """
    permission_classes = [TokenHasReadWriteScope]

    def get(self, request):
        user = request.user
        try:
            twitter_account_obj = TwitterAccount.objects.get(user=user, id=request.GET["id"])
            data = request.GET
            link = data["link"]


            api = Twython(consumer_key, consumer_secret, twitter_account_obj.access_token, twitter_account_obj.access_secret)
            tweet = api.show_status(id=int(link.split("status/")[1]))

            if len(TweetData.objects.filter(tweet_data__id=int(link.split("status/")[1])))!=0:
                return Response({"error":"tweet already submitted", "success":False}, status=400)


            if tweet["user"]["screen_name"] != twitter_account_obj.twitter_account_detail["screen_name"]:
                return Response({"error":"tweet id does not match with any of the user tweets",
                                 "success":False},status=400)

            return Response({"tweet_data":tweet, "success":True}, status=200)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)

    def post(self, request):
        user = request.user
        try:
            twitter_account_obj = TwitterAccount.objects.get(user=user, id=request.GET["id"])
            data = request.data
            link = data["link"]
            submission_date = data["date"] 
            tweet_work = data["like_retweet"]

            api = Twython(consumer_key, consumer_secret, twitter_account_obj.access_token,
                          twitter_account_obj.access_secret)
            tweet = api.show_status(id=int(link.split("status/")[1]))

            if len(TweetData.objects.filter(tweet_data__id=int(link.split("status/")[1]))) != 0:
                return Response({"error": "Tweet already submitted", "success": False}, status=400)

            if tweet["user"]["screen_name"] != twitter_account_obj.twitter_account_detail["screen_name"]:
                return Response({"error": "Tweet does not match with any of the user tweets",
                                 "success": False}, status=400)
            like = False
            like_retweet = False

            if tweet_work ==0:
                like = True

            elif tweet_work==1:
                like_retweet = True

            else:
                return Response({"error":"Invalid value", "success":False}, status=400)

            tweet_data_obj = TweetData.objects.create(
                account=twitter_account_obj,
                tweet_data=tweet,
                date_time_submitted=submission_date,
                url=link,
                likes=like,
                like_retweet = like_retweet
            )
            return Response({"tweet_data": tweet_data_obj.id, "success": True}, status=200)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)



class Choices(APIView):
    def get(self, request):
        try:
            return Response({"choices" :
                            ["GENERAL",
                            "SPORTS",
                            "MUSIC",
                            "ENTERTAINMENT",
                            "LIFESTYLE",
                            "GOVERNMENT&POLITICS",
                            "BUSINESS CEO",
                            "WOMEN&NGO'S",
                            "FASHION",
                            "NEWS",
                            "TECH",
                            "QUOTES",
                            "GRAPHICS DESIGNING",
                            "HEALTH",]}, status=200)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class SelectChoice(APIView):

    """METHOD POST: Selecting what type of twitter user likes to follow
       METHOD GET: Showing all the choices user made
    """

    permission_classes = [TokenHasReadWriteScope]
    def post(self, request):
        user = request.user
        try:

            data = request.data
            choices = data["choices"]
            user = User.objects.get(username=user.username, is_active=True)
            account_exists = False
            if TwitterAccount.objects.filter(user=user, is_deleted=False).exists():
                account_exists = True
            user_info = UserAccountInfo.objects.get(user=user)
            user_info.type_use = choices
            user_info.choices_made = True
            user_info.save()
            return Response({"success":True, "account_exists":account_exists}, status=201)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)

    def get(self, request):
        user = request.user
        try:
            user = User.objects.get(id=user.id, is_active=True)
            user_info = UserAccountInfo.objects.get(user=user)
            account_exists = False
            if TwitterAccount.objects.filter(user=user, is_deleted=False).exists():
                account_exists = True
            return Response({"choices":user_info.type_use, "account_exists":account_exists}, status=200)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)

class StatusInfo(APIView):

    def get(self, request):
        try:
            i_d = request.GET["id"]
            if i_d.isdigit():
                twitter_url_obj = TwitterUrl.objects.get(id=int(i_d))
                if twitter_url_obj.is_used:
                    return Response({"success":True}, status=200)
                else:
                    return Response({"success":False}, status=400)
            else:
                return Response({"success":False}, status=400)
        except Exception as e:
            traceback.print_exc()
            return Response({"success":False, "error":"internal server error"}, status=400)

class TweetList(APIView):
    permission_classes = [TokenHasReadWriteScope]

    def get(self, request):
        try:
            twitter_id = request.GET["id"]
            if twitter_id.isdigit():
                twitter_account = TwitterAccount.objects.get(id=int(twitter_id), is_deleted=False)
                screen_name = twitter_account.twitter_account_detail["screen_name"]
                profile_pic = twitter_account.twitter_account_detail["image_url"]
                user_info_obj = UserAccountInfo.objects.get(user=twitter_account.user)
                if twitter_account.subscription:
                    is_trial = False
                    rem = str(Subscription.objects.get(twitter_account=twitter_account.id).renewal_date - datetime.datetime.now()).split(",")[0]
                    pack = Subscription.objects.get(twitter_account=twitter_account.id).pack_price
                else:
                    is_trial = True
                    rem = str(user_info_obj.remaining_days) + " days"
                    pack = "trial"

                twitter_account_qs = TweetData.objects.filter(account=twitter_account).order_by("-id")
                response = [{"admin_verified" : x.admin_verified,
                             "is_active" : x.is_active,
                             "in_queue" : x.in_queue,
                             "is_done" : x.is_done,
                             "suspended" : x.suspended,
                             "likes" : x.likes,
                             "like_retweet" : x.like_retweet,
                             "url" : x.url, "id" : x.id} for x in twitter_account_qs]
                return Response({
                    "success":True,
                    "data":response,
                    "screen_name":screen_name,
                    "profile_pic":profile_pic,
                    "is_trial":is_trial,
                    "days_remaining":rem,
                    "pack":pack
                }, status=200)
            else:
                return Response({"success":False, "error":"Invalid value"}, status=400)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class TweetVerify(APIView):
    permission_classes = [TokenHasReadWriteScope]

    def post(self, request):
        user = request.user
        try:
            if user.is_superuser or user.is_staff:
                data = request.data
                tweet_id = data["tweet_id"]
                tweet_category = data["category"]
                date_time = data["date_time"]
                like = data["likes"]
                like_retweet = data["like_retweet"]
                suspend = data["suspend"]

                if tweet_category.strip() == "" or tweet_category==[] or not tweet_category:
                    return Response({"error" : "You must assign a category to the tweet"}, status=400)

                tweet_obj = TweetData.objects.get(id=tweet_id, is_active=False, in_queue=False, is_done=False, suspended=False)

                if suspend:
                    tweet_obj.suspended = True
                    tweet_obj.save()
                    message = "Your tweet associated with twitter account <font color='black'>@"+\
                          tweet_obj.account.twitter_account_detail["screen_name"]+" is disapproved </font>"
                    create_notification.delay(tweet_obj.account.user_id, message)
                    return Response({"message":"Tweet is suspended and will not be put into active queue"}, status=400)

                if tweet_obj.likes and not tweet_obj.like_retweet:
                    like = like
                    like_retweet = 0

                if (like + like_retweet) >= TwitterAccount.objects.filter(is_active=True).count():
                    return Response({
                        "error" : "Twitter accounts out of range. Please assign the tweet with or less than "+ str(TwitterAccount.objects.filter(is_active=True).count())+" twitter accounts."
                    }, status=400)

                tweet_obj.tweet_category = tweet_category
                tweet_obj.date_time_verified = date_time
                tweet_obj.admin_like_count = like
                tweet_obj.admin_like_retweet_count = like_retweet
                tweet_obj.save()
                user_id = tweet_obj.account.user_id
                assign_tweet_users.delay(tweet_obj.id, user_id)

                message = "Your tweet associated with twitter account <font color='black'>@"+\
                          tweet_obj.account.twitter_account_detail["screen_name"]+\
                          "</font> is verified for favoriting or retweeting with <font color='black'>"+str(like+like_retweet)+ \
                          "</font> other verified accounts and is now in active queue. You will be notified for every activity on your tweet by us"

                create_notification.delay(tweet_obj.account.user_id, message)
                return Response({"success":True, "message":"Tweet is in active queue"}, status=200)
            else:
                return Response({"error": "Invalid username/password", "success": False}, status=403)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


    def get(self, request):
        user = request.user
        try:

            if user.is_superuser or user.is_staff:
                response = []
                tweet_qs = TweetData.objects.all().order_by('-id')
                for x in tweet_qs:
                    if x.like_retweet:
                        tweet_type = "like_retweet"
                    else:
                        tweet_type = "like"
                    time_date = x.date_time_submitted
                    submit_date = datetime.datetime.strftime(time_date, "%Y-%m-%d %I:%M %p")
                    response.append({
                        "tweet_id" : x.id,
                        "user_id" : x.account.user_id,
                        "email" : x.account.user.email,
                        "twitter_account" : x.account.twitter_account_detail,
                        "twitter_id" : x.account_id,
                        "tweet_link" : x.url,
                        "admin_verified" : x.admin_verified,
                        "is_active" : x.is_active,
                        "in_queue" : x.in_queue,
                        "suspend" : x.suspended,
                        "is_done": x.is_done,
                        "is_active" : x.is_active,
                        "in_queue" : x.in_queue,
                        "like" : x.admin_like_count,
                        "like_retweet" : x.admin_like_retweet_count,
                        "tweet_type" : tweet_type,
                        "submit_date" : submit_date

                    })
                return Response({"data":response, "success":True}, status=200)
            else:
                return Response({"error": "Invalid username/password", "success": False}, status=403)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class TwitterAccountApi(APIView):
    permission_classes = [TokenHasReadWriteScope]

    def get(self, request):
        user = request.user
        try:
            if user.is_superuser or user.is_staff:
                user_qs = User.objects.filter(is_active=True).order_by('-id')
                response = []

                for i in user_qs:
                    user_account = UserAccountInfo.objects.get(user=i)
                    choices = user_account.type_use
                    tweet_list = []

                    for tw in TwitterAccount.objects.filter(user=i, is_deleted=False):
                        if tw.subscription:
                            sub_obj = Subscription.objects.get(twitter_account=tw.id)
                            is_trial = False
                            pack_price = sub_obj.pack_price
                            pack_description = sub_obj.pack_description
                            remaining_days = sub_obj.renewal_date - sub_obj.last_payment
                        else:
                            is_trial = True
                            pack_price = 0
                            pack_description = "trial"
                            remaining_days = user_account.remaining_days
                        tweet_list.append({
                            "id" : tw.id,
                            "twitter_account_detail" : tw.twitter_account_detail,
                            "is_active" : tw.is_active,
                            "is_deleted" : tw.is_deleted,
                            "access_revoked" : tw.access_revoked,
                            "subscription" : is_trial,
                            "pack_price" : pack_price,
                            "pack_description" : pack_description,
                            "remaining_days" : remaining_days,
                            "suspended" : tw.suspended,
                            "choices" : tw.type_use,
                            "allow_retweet" : tw.retweet_allow
                        })

                    response.append({
                        "email": i.email,
                        "mobile": i.username,
                        "user_id": i.id,
                        "is_active": True,
                        "choices": choices,
                        "country_code": user_account.country_code,
                        "twitter_account": tweet_list,
                        "is_staff": i.is_staff,
                        "is_superuser": i.is_superuser
                    })
                return Response({"data":response, "success":True}, status=200)
            else:
                return Response({"error": "Invalid username/password", "success": False}, status=403)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


    def post(self, request):
        user = request.user
        try:
            if user.is_superuser or user.is_staff:
                i_d = request.GET["id"]
                twitter_obj = TwitterAccount.objects.get(id=i_d, is_deleted=False)
                screen_name = twitter_obj.twitter_account_detail["screen_name"]
                data = request.data
                active = data["active"]
                suspend = data["suspend"]
                allow_retweet = data["allow_retweet"]

                if suspend:
                    twitter_obj.suspended = True
                    twitter_obj.save()
                    return Response({"message":"Twitter account is suspended and will not be used"}, status=400)

                if active:
                    twitter_obj.is_active = True
                    twitter_obj.retweet_allow = allow_retweet
                    twitter_obj.save()
                    message = "Your twitter account with screen name <font color='black'>@"+screen_name+" is now verified </font> and now you can " \
                                "post your tweets you want to get favourited or retweeted."
                    create_notification.delay(twitter_obj.user_id, message)
                elif not active:
                    twitter_obj.is_active = False
                    twitter_obj.retweet_allow = allow_retweet
                    twitter_obj.save()
                    message = "Your twitter account with screen name <font color='black'>@"+screen_name+" is deactivated </font> for indefinite time"
                    create_notification.delay(twitter_obj.user_id, message)
                else:
                    return Response({"error":"Invalid value provided", "success":False}, status=400)

                return Response({"success":True}, status=200)
            else:
                return Response({"error": "Invalid username/password", "success"
                                                                       "": False}, status=403)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class AdminLogin(APIView):
    """ This api is only for admin login and will return an error id user doesn't belon to the staff and superuser category"""

    def get(self, request):
        try:
            data = request.GET
            username = data["username"]
            password = data["password"]
            user = authenticate(username=username, password=password)
            if user:
                if user.is_superuser or user.is_staff:

                    if Application.objects.filter(user=user).exists():
                        app = Application.objects.get(user=user)
                    else:
                        app =Application.objects.create(user=user, client_type=Application.CLIENT_CONFIDENTIAL,authorization_grant_type=Application.GRANT_PASSWORD, name=user.username)

                    token_str = generate_token()
                    token = AccessToken.objects.create(
                        token = token_str,
                        application = app,
                        user = user,
                        scope = "read write",
                        expires = datetime.datetime.now() + datetime.timedelta(days=365)
                    )
                    return Response({
                        "token":token.token,
                        "client_secret":app.client_secret,
                        "client_id":app.client_id,
                        "scope":"read write",
                        "type":"Bearer"
                    }, status=200)
                else:
                    return Response({"error":"Invalid username/password", "success":False}, status=403)

            else:
                return Response({"error": "Invalid username/password", "success": False}, status=403)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":"Invalid username/password", "success":False}, status=400)


class ApproveDisapprove(APIView):
    permission_classes = [TokenHasReadWriteScope]

    def post(self, request):
        user = request.user
        try:
            if user.is_superuser or user.is_staff:
                twitter_account = TwitterAccount.objects.get(id=request.GET["id"])
                data = request.data
                approve_disapprove = data["approve_disapprove"]
                if approve_disapprove == 0:
                    twitter_account.is_active = True
                    twitter_account.suspended = False
                    twitter_account.save()
                elif approve_disapprove == 1:
                    twitter_account.is_active = False
                    twitter_account.suspended = True
                    twitter_account.save()
                else:
                    return Response({"error":"Invalid value provided"}, status=400)

                return Response({"success":True}, status=200)
            else:
                return Response({"error":"Invalid username/password"}, status=400)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


class SelectTwitterChoice(APIView):

    permission_classes = [TokenHasReadWriteScope]

    def post(self, request):
        user = request.user
        try:
            data = request.data
            twiiter_account = TwitterAccount.objects.get(id=request.GET["id"], user=user, suspended=False)
            choices = data["choices"]
            if isinstance(choices, list):
                twiiter_account.type_use = choices
                twiiter_account.save()
                return Response({"success" : True},status=200)
            else:
                return Response({"error" : "Invalid value provided", "success" : False}, status=400)
        except Exception as e:
            traceback.print_exc()
            return Response({"error" : str(e), "success" : False}, status=400)

    def get(self, request):
        user = request.user
        try:
            twitter_account = TwitterAccount.objects.get(user=user, id=request.GET["id"], suspended=False)
            if twitter_account.type_use:
                choices = True
            else:
                choices = False
            return Response({
                "id" : twitter_account.id,
                "choice_category" : twitter_account.type_use,
                "choices" : choices,
                "is_active" : twitter_account.is_active
            })
        except Exception as e:
            return Response({"error" : str(e), "success" : False}, status=400)


class Statistics(APIView):
    permission_classes = [TokenHasReadWriteScope]

    def get(self, request):
        user = request.user
        try:
            if user.is_superuser or user.is_staff:
                twitter_account_qs = TwitterAccount.objects.all()
                tweet_qs = TweetData.objects.all()
                response = {
                    "total_twitter_account" : twitter_account_qs.count(),
                    "total_active_twitter_account" : twitter_account_qs.filter(is_active=True).count(),
                    "total_suspended_twitter_account" : twitter_account_qs.filter(suspended=True).count(),
                    "total_deleted_twitter_account" : twitter_account_qs.filter(is_deleted=True).count(),
                    "total_pending_twitter_account" : twitter_account_qs.filter(is_active=False, suspended=False, is_deleted=False).count(),
                    "total_tweet" : tweet_qs.count(),
                    "total_progress_tweet" : tweet_qs.filter(is_active=True, in_queue=True).count(),
                    "total_done_tweet" : tweet_qs.filter(is_done=True).count(),
                    "total_suspended_tweet" : tweet_qs.filter(suspended=True).count(),
                }
                return Response(response, status=200)
            else:
                return Response({"error" : "Invalid username/password"}, status=400)
        except Exception as e:
            traceback.print_exc()
            return Response({"error" : str(e)}, status=400)


class Search(APIView):
    permission_classes = [TokenHasReadWriteScope]
    def get(self, request):
        user = request.user
        try:
            if user.is_superuser or user.is_staff:
                query = request.GET["query"]
                if query.lower() == "email":
                    email = request.GET["email"]
                    user_qs = User.objects.filter(email__istartswith=email, is_active=True)
                elif query.lower() == "screen_name":
                    name = request.GET["name"]
                    twitter_qs = TwitterAccount.objects.filter(is_deleted=False, twitter_account_detail__screen_name__istartswith=name)
                    user_qs = User.objects.filter(id__in=twitter_qs.values('user_id'), is_active=True)

                else:
                    user_qs = User.objects.filter(is_active=True)

                response = []
                for i in user_qs:
                    user_account = UserAccountInfo.objects.get(user=i)
                    tweet_list = []
                    for tw in TwitterAccount.objects.filter(user=i, is_deleted=False):
                        if tw.subscription:
                            sub_obj = Subscription.objects.get(twitter_account=tw.id)
                            is_trial = False
                            pack_price = sub_obj.pack_price
                            pack_description = sub_obj.pack_description
                            remaining_days = sub_obj.renewal_date - sub_obj.last_payment
                        else:
                            is_trial = True
                            pack_price = 0
                            pack_description = "trial"
                            remaining_days = user_account.remaining_days
                        tweet_list.append({
                            "id" : tw.id,
                            "twitter_account_detail" : tw.twitter_account_detail,
                            "is_active" : tw.is_active,
                            "is_deleted" : tw.is_deleted,
                            "access_revoked" : tw.access_revoked,
                            "subscription" : is_trial,
                            "pack_price" : pack_price,
                            "pack_description" : pack_description,
                            "remaining_days" : remaining_days,
                            "suspended" : tw.suspended,
                            "choices" : tw.type_use
                        })

                    response.append({
                        "email": i.email,
                        "mobile": i.username,
                        "user_id": i.id,
                        "is_active": True,
                        "choices": [],
                        "country_code": user_account.country_code,
                        "twitter_account": tweet_list,
                        "is_staff": i.is_staff,
                        "is_superuser": i.is_superuser
                    })
                return Response({"data":response, "success":True}, status=200)
            else:
                return Response({"error" : "invalid username/password"}, status=403)
        except Exception as e:
            traceback.print_exc()
            return Response({"error" : str(e)}, status=400)

class ChoiceUserCount(APIView):

    permission_classes = [TokenHasReadWriteScope]

    def get(self, request):
        user = request.user
        try:
            if user.is_superuser or user.is_staff:
                choices = request.GET["choices"]
                tweet_id = request.GET["tweet_id"]
                tweet_data = TweetData.objects.get(id=tweet_id)
                twitter_account = TwitterAccount.objects.filter(
                    is_active=True,
                    is_deleted=False,
                    suspended=False,
                ).exclude(id=tweet_data.account_id)

                twitter_count = [x.id for x in twitter_account if choices in x.type_use]
                return Response({
                    "message" : "There are "+str(len(twitter_count))+ " active twitter accounts for the "+ choices+" category."
                }, status=200)
            else:
                return Response({"error" : "invalid username/password"}, status=403)
        except Exception as e:
            traceback.print_exc()
            return Response({"error" : str(e)}, status=400)