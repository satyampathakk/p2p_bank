from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal
from .models import Account, Transaction
import stripe
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def dashboard(request):
    account = Account.objects.get(user=request.user)
    transactions = Transaction.objects.filter(account=account).order_by('-timestamp')[:10]
    return render(request, 'accounts/dashboard.html', {
        'account': account,
        'transactions': transactions
    })

@login_required
def deposit(request):
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount'))
        try:
            # Create Stripe payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency='usd',
            )
            
            # Create transaction record
            account = Account.objects.get(user=request.user)
            Transaction.objects.create(
                account=account,
                transaction_type='DEP',
                amount=amount,
                status='pending'
            )
            
            return JsonResponse({
                'clientSecret': intent.client_secret,
                'amount': amount
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return render(request, 'accounts/deposit.html', {
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY
    })

@login_required
def withdraw(request):
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount'))
        account = Account.objects.get(user=request.user)
        
        if account.balance >= amount:
            account.balance -= amount
            account.save()
            
            Transaction.objects.create(
                account=account,
                transaction_type='WTH',
                amount=amount
            )
            
            messages.success(request, f'Successfully withdrew ${amount}')
        else:
            messages.error(request, 'Insufficient funds')
        
        return redirect('dashboard')
    
    return render(request, 'accounts/withdraw.html')

@login_required
def transfer(request):
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount'))
        recipient_account_number = request.POST.get('recipient_account')
        
        try:
            sender_account = Account.objects.get(user=request.user)
            recipient_account = Account.objects.get(account_number=recipient_account_number)
            
            if sender_account.balance >= amount:
                # Create transfer transaction
                sender_account.balance -= amount
                recipient_account.balance += amount
                
                sender_account.save()
                recipient_account.save()
                
                Transaction.objects.create(
                    account=sender_account,
                    transaction_type='TRF',
                    amount=amount,
                    recipient=recipient_account
                )
                
                messages.success(request, f'Successfully transferred ${amount} to account {recipient_account_number}')
            else:
                messages.error(request, 'Insufficient funds')
                
        except Account.DoesNotExist:
            messages.error(request, 'Recipient account not found')
        
        return redirect('dashboard')
    
    return render(request, 'accounts/transfer.html')

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except stripe.error.SignatureVerificationError as e:
        return JsonResponse({'error': str(e)}, status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        amount = Decimal(payment_intent.amount) / 100  # Convert from cents
        
        # Update account balance and transaction status
        try:
            transaction = Transaction.objects.get(
                status='pending',
                amount=amount
            )
            account = transaction.account
            account.balance += amount
            account.save()
            
            transaction.status = 'completed'
            transaction.save()
            
        except Transaction.DoesNotExist:
            return JsonResponse({'error': 'Transaction not found'}, status=400)

    return JsonResponse({'status': 'success'})