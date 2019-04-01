from django.contrib import admin
from .models import TwitterAccount, TwitterUrl, TweetData, UserAccountInfo, TweetUsers, LikeRetweetData
# Register your models here.

admin.site.register(TwitterAccount)
admin.site.register(TwitterUrl)
admin.site.register(TweetData)
admin.site.register(UserAccountInfo)
admin.site.register(TweetUsers)
admin.site.register(LikeRetweetData)
