# payments/admin.py
from django.contrib import admin
from .models import UserPayment

@admin.register(UserPayment)
class UserPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'product_name', 'price', 'currency', 'has_paid', 'stripe_checkout_id', 'stripe_customer_id')
    search_fields = ('user__email', 'stripe_customer_id')
