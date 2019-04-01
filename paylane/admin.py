from django.contrib import admin
from .models import Subscription, TransactionStatus, ContactUs
# Register your models here.

admin.site.register(Subscription)
admin.site.register(TransactionStatus)
admin.site.register(ContactUs)