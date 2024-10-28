from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal
from .models import Account, Transaction
import stripe
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import razorpay
import json
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
        data = json.loads(request.body)
        am = Decimal(data.get('amount'))
        print(am)
        amount = am
        
        # Initialize Razorpay client
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        try:
            # Create Razorpay order
            order_data = {
                'amount': int(amount * 100),  # Convert to paise
                'currency': 'INR',  # Change to INR if you're using Indian currency
                'payment_capture': '1'  # Auto capture payment
            }
            order = client.order.create(data=order_data)

            # Create transaction record
            account = Account.objects.get(user=request.user)
            Transaction.objects.create(
                account=account,
                transaction_type='DEP',
                amount=amount,
                status='pending'
            )
            return JsonResponse({
                'orderId': order['id'],  # Return the order ID to the client
                'amount': amount
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return render(request, 'accounts/deposit.html', {
        'razorpay_key_id': settings.RAZORPAY_KEY_ID  # Pass Razorpay key to the template
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

@login_required
def confirm_payment(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        payment_id = data.get('payment_id')
        amount = data.get('amount')

        try:
            # Initialize Razorpay client
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            payment = client.payment.fetch(payment_id)

            # Check if payment is captured
            if payment['status'] == 'captured':
                # Payment was successful
                account = Account.objects.get(user=request.user)
                account.balance += Decimal(amount)  # Update the account balance
                account.save()

                # Create transaction record
                Transaction.objects.create(
                    account=account,
                    transaction_type='DEP',
                    amount=Decimal(amount),
                    status='completed'  # Update status here
                )

                return JsonResponse({'success': True})
            else:
                return JsonResponse({'error': 'Payment not captured'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request'}, status=400)
