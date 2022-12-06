from django.db.models import F
from django.db.transaction import atomic
from rest_framework import serializers

from bank.models import Transaction, Account

permissions = [
    ('client', 'Client'),
    ('moderator', 'Moderator'),
    ('administrator', 'Administrator')
]


class TransactionSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Transaction
        fields = [
            'url',
            'sender_id',
            'recipient_id',
            'amount',
            'timestamp',
            'owner'
        ]

    @atomic()
    def create(self, validated_data: dict) -> Transaction:
        sender: Account = validated_data.get('sender_id')
        recipient: Account = validated_data.get('recipient_id')
        amount = validated_data.get('amount')

        if sender == recipient:
            raise Exception('The sender and the recipient must not be the same')
        if sender.balance < amount:
            raise Exception('Not enough funds')

        Account.objects.filter(user_id=sender.user_id).update(
            balance=F('balance') - amount
        )
        Account.objects.filter(user_id=recipient.user_id).update(
            balance=F('balance') + amount
        )
        return Transaction.objects.create(
            sender_id=sender, recipient_id=recipient, amount=amount
        )


class AccountSerializer(serializers.HyperlinkedModelSerializer):
    transactions = serializers.HyperlinkedRelatedField(
        many=True, view_name='transaction-detail', read_only=True
    )
    user_id = serializers.CharField(write_only=True)

    class Meta:
        model = Account
        fields = ['url', 'id', 'user_id', 'balance', 'transactions']


class AccountCreated(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Account
        fields = ['url', 'id', 'user_id', 'balance']


class AccountCreateSerializer(serializers.Serializer):
    name = serializers.CharField(write_only=True, required=True)
    surname = serializers.CharField(write_only=True, required=True)
    phone = serializers.CharField(write_only=True, required=True)
    city = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)
    permission = serializers.CharField(
        write_only=True, default='client', initial='client'
    )
