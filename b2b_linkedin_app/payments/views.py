# app/payments/views.py
import stripe
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render
from authorization.models import User
from authorization.utils import create_one_time_sub
from .models import UserPayment
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

# --- 1. Create One-Time Payment Checkout Session ---
def create_one_time_checkout(request):
    if request.method == 'GET':
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='payment',
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': 5000,
                        'product_data': {
                            'name': 'One-Time Access',
                        },
                    },
                    'quantity': 1,
                },
            ],
            metadata={
                'user_id': request.user.id,
                'type': 'one_time'
            },
            customer_email=request.user.email,
            success_url='http://localhost:8001/payment/success/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='http://localhost:8001/payment/cancel/'
        )

        create_one_time_sub(request.user)

        return redirect(session.url)

    return HttpResponseNotAllowed(['GET'])

# --- 2. Create Subscription Checkout Session ---
def create_subscription_checkout(request):
    if request.method == 'POST':
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',
            line_items=[
                {
                    'price': settings.STRIPE_SUBSCRIPTION_PRICE_ID,  # predefined in Stripe dashboard
                    'quantity': 1,
                },
            ],
            metadata={
                'user_id': request.user.id,
                'type': 'subscription'
            },
            customer_email=request.user.email,
            success_url='https://yourdomain.com/payment/success/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://yourdomain.com/payment/cancel/',
        )

        return redirect(session.url)


# --- 3. Webhook to Set is_paid ---
@require_POST
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        logger.info(f"Received event: {event['type']}")
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning(f"Stripe webhook error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

    event_type = event['type']

    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata'].get('user_id')
        payment_type = session['metadata'].get('type')
        user = User.objects.filter(id=user_id).first()

        if user:
            UserPayment.objects.create(
                user=user,
                stripe_checkout_id=session.id,
                stripe_customer_id=session.get('customer'),
                product_name=payment_type,
                has_paid=True,
                price=session['amount_total'] / 100,
                currency=session['currency'],
            )


            if payment_type == 'one_time':
                user.one_time_paid = True
                user.is_paid = True
            elif payment_type == 'subscription':
                user.is_paid = True

            user.save()

    elif event_type == 'customer.subscription.deleted':
        customer_id = event['data']['object']['customer']
        user_payment = UserPayment.objects.filter(stripe_customer_id=customer_id).last()
        if user_payment:
            user = user_payment.user
            user.is_paid = False
            user.save()

    else:
        logger.info(f"Ignoring unhandled event type: {event_type}")

    return JsonResponse({'status': 'ok'})


def payment_success(request):
    session_id = request.GET.get('session_id')
    if not session_id:
        return redirect('/')

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        logger.warning(f"Stripe session fetch failed: {e}")
        return redirect('/')

    return redirect('/admin/')


def payment_cancel(request):
    return render(request, 'payments/cancel.html')