from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from .forms import RegistrationForm

def register(request):
    if request.user.is_authenticated:
        return redirect('post_login_redirect')


    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])

            # Даём доступ к админке
            user.is_staff = True
            user.save()

            user = authenticate(request, email=user.email, password=form.cleaned_data['password'])
            if user is not None:
                login(request, user)
                return redirect('post_login_redirect')
    else:
        form = RegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def post_login_redirect(request):
    user = request.user

    if not user.one_time_paid:
        return redirect('stripe_one_time_checkout')

    if user.one_time_paid and not user.is_paid:
        return redirect('stripe_subscription_checkout')

    return redirect('/admin/')  # 🎯 Всё доступно
