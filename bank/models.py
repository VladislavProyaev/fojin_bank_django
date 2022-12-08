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

    def __str__(self) -> str:
        return (
            f'Amount {self.amount} From Account {self.sender_id} '
            f'To Account {self.recipient_id}'
        )


class Account(models.Model):
    user_id = models.IntegerField()
    balance = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f'Account {self.id}'
