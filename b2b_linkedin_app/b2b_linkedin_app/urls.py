"""
URL configuration for b2b_linkedin_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from payments.urls import urlpatterns as payment_urls
from parser_controler.urls import urlpatterns as parser_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('authorization.urls')),
    path('payment/', include(payment_urls)),
    path('login/', auth_views.LoginView.as_view(), name='login'),  # встроенный шаблон
    path("", include(parser_urls)),

]
