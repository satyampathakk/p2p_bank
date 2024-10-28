from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Account(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Account ({self.account_number})"

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('DEP', 'Deposit'),
        ('WTH', 'Withdrawal'),
        ('TRF', 'Transfer'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    recipient = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, related_name='received_transactions')
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='completed')
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.timestamp}"

@receiver(post_save, sender=User)
def create_account(sender, instance, created, **kwargs):
    if created:
        import random
        account_number = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        Account.objects.create(user=instance, account_number=account_number)