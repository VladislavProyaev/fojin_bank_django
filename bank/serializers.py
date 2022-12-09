from django.db.transaction import atomic
from rest_framework import serializers
from rest_framework.exceptions import APIException

from bank.models import Transaction, Account


class TransactionError(APIException):
    status_code = 422
    default_detail = 'Something wont wrong. Please try again later.'
    default_code = 'something_wont_wrong'


class TransactionSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all()
    )
    recipient_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all()
    )

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
            raise TransactionError(
                detail='The sender and the recipient must not be the same'
            )
        if sender.balance < amount:
            raise TransactionError(detail='Not enough funds')

        sender.balance -= amount
        sender.save()
        recipient.balance += amount
        recipient.save()

        return Transaction.objects.create(
            sender_id=sender, recipient_id=recipient, amount=amount
        )


class AccountSerializer(serializers.HyperlinkedModelSerializer):
    transactions = serializers.HyperlinkedRelatedField(
        many=True, view_name='transaction-detail', read_only=True
    )

    class Meta:
        model = Account
        fields = ['url', 'id', 'user_id', 'balance', 'transactions']


class AccountPUTSerializer(serializers.HyperlinkedModelSerializer):
    transactions = serializers.HyperlinkedRelatedField(
        many=True, view_name='transaction-detail', read_only=True
    )
    user_id = serializers.CharField(read_only=True)

    class Meta:
        model = Account
        fields = ['url', 'id', 'user_id', 'balance', 'transactions']
