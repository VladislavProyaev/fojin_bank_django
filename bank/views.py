from django.http import QueryDict
from rest_framework import viewsets, status
from rest_framework.request import Request
from rest_framework.response import Response

from bank.models import Transaction, Account
from bank.permissions import IsOwnerOrReadOnly
from bank.serializers import TransactionSerializer, AccountSerializer
from common.endpoints import EndPoints
from services import rabbit_mq


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsOwnerOrReadOnly]


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    # permission_classes = [IsOwnerOrReadOnly]
    #
    # def permission_denied(self, request, message=None, code=None):
    #     raise PermissionDenied()

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

        user_accounts = Account.objects.filter(user_id=kwargs['user_id']).all()
        serializer = self.get_serializer(user_accounts, many=True)
        return Response(serializer.data)
