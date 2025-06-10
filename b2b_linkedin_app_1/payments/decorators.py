from django.shortcuts import redirect
from functools import wraps

def check_payment_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return redirect('login')

        if not user.one_time_paid:
            return redirect('stripe_one_time_checkout')

        if user.one_time_paid and not user.is_paid:
            return redirect('stripe_subscription_checkout')

        return view_func(request, *args, **kwargs)

    return _wrapped_view
