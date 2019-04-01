from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope
from paylane.paylane_rest_client import client
from tweet_account.models import TwitterAccount
from paylane.models import Subscription, ContactUs
from paylane.tasks import trial_off, send_query
from django.conf import settings
import traceback
import datetime
import requests
import json
# Create your views here.


def generate_token(card, cvv, name, month, year):

    url = "https://direct.paylane.com/rest.js/cards/generateToken"
    data = {
        "public_api_key":settings.PAYLANE_API_KEY,
        "card_number":card,
        "expiration_month":month,
        "expiration_year":year,
        "name_on_card":name,
        "card_code":cvv}

    token_request = requests.post(url, data=json.dumps(data))
    token = json.loads(token_request.text)
    print(token, ">>>>>>>>>")
    if not token["success"]:
        return token
    check_card = client.check_card_by_token({"token":token["token"]})
    token.update(check_card)
    return token


class PaylaneApi(APIView):
    permission_classes = [TokenHasReadWriteScope]

    def post(self, request):
        user = request.user
        try:
            data = request.data
            i_d = request.GET["id"]
            street_house = data["street_house"]
            city = data["city"]
            state = data["state"]
            zip = data["zip"]
            country_code = data["country_code"]
            email = data["email"]
            amount = data["amount"]
            description = data["description"]
            currency = data["currency"]
            cc_number = data["cc_number"]
            cvv = data["cvv"]
            name = data["name"]
            month = data["month"]
            year = data["year"]
            date_time = data["date_time"]
            previous_sub_ids = []

            twitter_account = TwitterAccount.objects.get(id=i_d, is_deleted=False, is_active=True, access_revoked=False)
            if Subscription.objects.filter(twitter_account=twitter_account.id, is_active=True).exists():
                previous_sub_ids = [x.id for x in Subscription.objects.filter(twitter_account=twitter_account.id, is_active=True)]
            token = generate_token(cc_number, cvv, name, month, year)
            if not token["success"]:
                return Response(token, status=400)

            card_params = {
                'sale': {
                    'amount': float(amount),
                    'currency': currency,
                    'description': description
                },
                'customer': {
                    'name': name,
                    'email': email,
                    'ip': '127.0.0.1',
                    'address': {
                        'street_house': street_house,
                        'city': city,
                        'state': state,
                        'zip': zip,
                        'country_code': country_code
                    }
                },
                'card': {
                    'token': token["token"]
                }
            }
            status = client.card_sale_by_token(card_params)
            print(status, type(status), ">>>>>>>>>>>>>>>>.")
            if status["success"]:

                detail = {
                    "twitter_detail": twitter_account.twitter_account_detail,
                    "user_detail": {
                        "email": user.email,
                        "mobile": user.username,
                    }
                }

                subscription_obj = Subscription.objects.create(
                    twitter_account = twitter_account.id,
                    twitter_account_detail = detail,
                    subscription_bought = date_time,
                    last_payment = date_time,
                    sale = status["id_sale"],
                    p_account = status["id_account"],
                    pack_price = amount,
                    pack_description = description+" #1",
                    currency = currency.upper(),
                    is_active = True
                )
                subscription_obj.payment_date_time = [date_time]
                subscription_obj.renewal_date = datetime.datetime.strptime(date_time, "%Y-%m-%d %H:%M") + datetime.timedelta(days=30)
                subscription_obj.save()
                twitter_account.subscription = True
                twitter_account.save()
                trial_off.delay(user.id)
                if len(previous_sub_ids) != 0:
                    Subscription.objects.filter(id__in=previous_sub_ids).update(is_active=False)
                return Response({"success":True}, status=200)

            else:
                return Response(status, status=400)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)

    def get(self, request):
        try:
            twitter_account = TwitterAccount.objects.get(id=request.GET["id"], is_active=True)
            if twitter_account.subscription:
                subscription_obj = Subscription.objects.get(twitter_account=twitter_account.id, is_active=True)
                response = {
                    "subscription_id": subscription_obj.id,
                    "id": twitter_account.id,
                    "pack": subscription_obj.pack_price,
                    "description": subscription_obj.pack_description,
                    "message" : "subscription exists for this account"
                }
                return Response(response, status=200)
            else:
                return Response({"error":"no subscription exists for this account"}, status=400)

        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "status":400})


class CardType(APIView):
    def post(self, request):
        try:
            data = request.data
            card = data["card"]
            check_card = client.check_card({"card_number":card})
            return Response(check_card)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e)}, status=400)


class ContactusApi(APIView):

    def post(self, request):
        user = request.user
        try:
            data = request.data
            email = data["email"]
            mobile = data.get("mobile")
            subject = data["subject"]
            message = data["message"]

            if not request.user.is_anonymous:
                email = request.user.email
                mobile = request.user.username

            contact_us = ContactUs.objects.create(
                email = email,
                mobile = mobile,
                subject = subject,
                message = message
            )
            content = message +"\n"+mobile
            send_query.delay(contact_us.id, email, subject, content)
            return Response({
                "message" : "Thanks for contacting us. We have received your query and will get back to you soon.",
                "id" : contact_us.id
            }, status=200)
        except Exception as e:
            traceback.print_exc()
            return Response({"error" : str(e)}, status=400)
