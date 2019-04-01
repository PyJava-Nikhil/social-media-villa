from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class Notifcation(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification = models.TextField(null=True, blank=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-id"]