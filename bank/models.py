from django.db import models


class Transaction(models.Model):
    sender_id = models.ForeignKey(
        'Account',
        related_name='sender_transactions',
        on_delete=models.CASCADE
    )
    recipient_id = models.ForeignKey(
        'Account',
        related_name='recipient_transactions',
        on_delete=models.CASCADE
    )
    amount = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']


class Account(models.Model):
    user_id = models.IntegerField(unique=True)
    balance = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f'ID: {self.id}'
