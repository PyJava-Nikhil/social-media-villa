from django.urls import path
from . import views

urlpatterns = [
    path(r'notification/', views.NotificationData.as_view(), name="notification_data")
]