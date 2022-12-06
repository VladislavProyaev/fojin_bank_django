from typing import Type

from django.http import QueryDict
from rest_framework import serializers, viewsets, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response

from bank.models import Transaction, Account
from bank.permissions import IsOwnerOrReadOnly
from bank.serializers import TransactionSerializer, AccountSerializer, \
    AccountCreateSerializer
from common.endpoints import EndPoints
from services import rabbit_mq


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsOwnerOrReadOnly]


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def permission_denied(self, request, message=None, code=None):
        raise PermissionDenied()

    def get_serializer_class(self) -> Type[serializers.Serializer]:
        if self.action == 'create':
            return AccountCreateSerializer

        return self.serializer_class

    def get_serializer(self, *args, **kwargs):
        base_serializer = kwargs.get('base_serializer')
        if base_serializer is not None:
            serializer_class = self.serializer_class
            del kwargs['base_serializer']
        else:
            serializer_class = self.get_serializer_class()
        kwargs.setdefault('context', self.get_serializer_context())
        return serializer_class(*args, **kwargs)

    @rabbit_mq.query(EndPoints.REGISTRATION)
    def create(self, request: Request, *args, **kwargs) -> Response:
        if not kwargs:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        data = QueryDict(mutable=True)
        for key, value in kwargs.items():
            data[key] = str(value)

        serializer = self.get_serializer(data=data, base_serializer=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        response = Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )
        access_token = f"{kwargs['token_type']} {kwargs['access_token']}"

        response.set_cookie('refresh_token', kwargs['refresh_token'])
        response.set_cookie('Authorization', access_token)

        return response

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
