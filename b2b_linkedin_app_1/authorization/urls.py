from django.urls import path
from .views import register, post_login_redirect    

urlpatterns = [
    path('', register, name='register'),
    path('post-login/', post_login_redirect, name='post_login_redirect'),
]