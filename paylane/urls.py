from django.urls import path
from . import views

urlpatterns = [
    path(r'check_card/', views.CardType.as_view(), name="check_card"),
    path(r'card_data/', views.PaylaneApi.as_view(), name="data_api"),
    path(r'contact_us/', views.ContactusApi.as_view(), name="contact_us"),
]