from django.db.models import Q
from django.http import QueryDict
from rest_framework import viewsets, status, mixins
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bank.models import Transaction, Account
from bank.permissions import IsOwnerOrReadOnly
from bank.serializers import TransactionSerializer, AccountSerializer, \
    AccountPUTSerializer
from common.endpoints import EndPoints
from services import rabbit_mq


class NoPermission(APIException):
    status_code = 401
    default_detail = 'You do not have permission for this!'
    default_code = 'no_permission'


class AccountNotFound(APIException):
    status_code = 404
    default_detail = 'Account Not Found'
    default_code = 'account_not_found'


class IncorrectAmount(APIException):
    status_code = 400
    default_detail = 'Amount should be more then 0'
    default_code = 'incorrect_amount'


class TransactionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    GenericViewSet
):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsOwnerOrReadOnly]

    @rabbit_mq.query(EndPoints.GET_USER)
    def list(self, request, *args, **kwargs):
        if not kwargs:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        is_super_permission = kwargs['is_super_permission']
        if is_super_permission:
            user_transactions = Transaction.objects.all()
        else:
            user_id = int(kwargs['user_id'])
            user_transactions = Transaction.objects.filter(
                Q(sender_id__user_id=user_id) | Q(recipient_id__user_id=user_id)
            ).all()
        serializer = self.get_serializer(user_transactions, many=True)
        return Response(serializer.data)

    @rabbit_mq.query(EndPoints.GET_USER)
    def create(self, request: Request, *args, **kwargs):
        sender_id = request.data['sender_id']
        account_id = kwargs['user_id']
        recipient_id = request.data['recipient_id']
        amount = request.data['amount']

        if amount <= 0:
            raise IncorrectAmount()

        try:
            account = Account.objects.get(pk=sender_id)
        except Account.DoesNotExist:
            raise AccountNotFound('Sender account not found!')
        try:
            Account.objects.get(pk=recipient_id)
        except Account.DoesNotExist:
            raise AccountNotFound('Recipient account not found!')
        if account.user_id != account_id:
            raise NoPermission()

        return super().create(request, *args, **kwargs)


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    permission_classes = [IsOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'update':
            return AccountPUTSerializer
        return self.serializer_class

    def permission_denied(self, request, message=None, code=None):
        raise PermissionDenied()

    @rabbit_mq.query(EndPoints.GET_USER)
    def create(self, request: Request, *args, **kwargs) -> Response:
        if not kwargs:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        data = QueryDict(mutable=True)
        for key, value in kwargs.items():
            data[key] = str(value)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        response = Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

        return response

    @rabbit_mq.query(EndPoints.GET_USER)
    def list(self, request, *args, **kwargs):
        if not kwargs:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        is_super_permission = kwargs['is_super_permission']
        if is_super_permission:
            user_accounts = Account.objects.all()
        else:
            user_accounts = (
                Account.objects.filter(user_id=kwargs['user_id']).all()
            )
        serializer = self.get_serializer(user_accounts, many=True)
        return Response(serializer.data)

    @rabbit_mq.query(EndPoints.GET_USER)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
