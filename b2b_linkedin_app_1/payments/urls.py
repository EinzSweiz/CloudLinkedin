# payments/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('one-time/', views.create_one_time_checkout, name='stripe_one_time_checkout'),
    path('subscribe/', views.create_subscription_checkout, name='stripe_subscription_checkout'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('success/', views.payment_success, name='stripe_success'),
    path('cancel/', views.payment_cancel, name='stripe_cancel'),

]
