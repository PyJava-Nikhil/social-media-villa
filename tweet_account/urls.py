from django.urls import path
from . import views

urlpatterns = [
    path(r'', views.index),
    path(r'signup/', views.SignUp.as_view(), name='signup_url'),
    path(r'login/', views.Login.as_view(), name='login_url'),
    path(r'add/', views.AddTwitterAccount.as_view(), name='add twitter account'),
    path(r'submit_tweet/', views.SubmitTweet.as_view(), name='get_status'),
    path(r'get_choices/', views.Choices.as_view(), name="choice"),
    path(r'select_choice/', views.SelectChoice.as_view(), name="select_choice"),
    path(r'status_info/', views.StatusInfo.as_view(), name="check_status"),
    path(r'tweet_list/', views.TweetList.as_view(), name="tweet_list"),
    path(r'verify_tweet/', views.TweetVerify.as_view(), name="tweet_admin_verify"),
    path(r'change_password', views.ChangePassword.as_view(), name="change_password"),
    path(r'forgot_password/', views.ForgotPassword.as_view(), name="forgot_password"),
    path(r'forgot_password_verify/', views.VerifyForgot.as_view(), name="verify_forgot_password"),
    path(r'mobile_email_check/', views.MobileEmailCheck.as_view(), name="mobile_email_check"),
    path(r'accounts/', views.TwitterAccountApi.as_view(), name="twitter_account_list"),
    path(r'admin_login/',views.AdminLogin.as_view(), name="admin_login"),
    path(r'activate/', views.Activation.as_view(), name="activate"),
    path(r'approve_disapprove/', views.ApproveDisapprove.as_view(), name="approve_disapprove account"),
    path(r'twitter_choice/', views.SelectTwitterChoice.as_view(), name="twitter_account_choices"),
    path(r'statistics/', views.Statistics.as_view(), name="statistics"),
    path(r'search/', views.Search.as_view(), name="search_api"),
    path(r'choicecount/', views.ChoiceUserCount.as_view(), name="choice_count_twitter"),
]
