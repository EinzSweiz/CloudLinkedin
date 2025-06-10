# b2b_linkedin_app/middleware/payment_required_middleware.py

from django.shortcuts import redirect
from django.urls import reverse

EXCLUDED_PATHS = [
    '/payment/one-time/',
    '/payment/subscribe/',
    '/payment/webhook/',
    '/admin/logout/',
]

class PaymentRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/') and request.path not in EXCLUDED_PATHS:
            user = request.user
            if user.is_authenticated:
                if user.is_superuser:
                    return self.get_response(request)
                if not user.one_time_paid:
                    return redirect(reverse('stripe_one_time_checkout'))
                elif not user.is_paid:
                    return redirect(reverse('stripe_subscription_checkout'))

        return self.get_response(request)
