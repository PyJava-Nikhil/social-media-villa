from django.shortcuts import render
from notification.models import Notifcation
from rest_framework.views import APIView
from rest_framework.response import Response
from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope
import traceback
# Create your views here.

class NotificationData(APIView):

    permission_classes = [TokenHasReadWriteScope]

    def get(self, request):
        user = request.user

        try:
            notification_qs = Notifcation.objects.filter(user=user)
            response = [{
                "message": i.notification,
                "read": i.read,
                "id": i.id
            } for i in notification_qs]
            return Response(response, status=200)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e), "success":False}, status=400)


    def post(self, request):
        user = request.user

        try:
            query = request.GET["query"]

            if query=="all":
                notification_qs = Notifcation.objects.filter(user=user).update(read=True)
            else:
                notification_obj = Notifcation.objects.get(id=request.GET["id"])
                notification_obj.read = True
                notification_obj.save()
            return Response({"success":True}, status=200)
        except Exception as e:
            traceback.print_exc()
            return Response({"error":str(e)}, status=400)
