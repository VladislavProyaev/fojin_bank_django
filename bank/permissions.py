from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import permissions
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.viewsets import ViewSetMixin

from bank.models import Transaction, Account
from services import rabbit_mq
from services.jwt_manager import JWTManager

if TYPE_CHECKING:
    from bank.views import TransactionViewSet, AccountViewSet


class IsOwnerOrReadOnly(permissions.BasePermission):

    @rabbit_mq.validate_action()
    def has_permission(
        self, request: Request, view: type[ViewSetMixin], **kwargs
    ) -> bool:
        available = kwargs.get('available')
        if available is not None:
            return available

        encoding_cookies = JWTManager.encode_token(request.COOKIES)
        if encoding_cookies is None:
            return True

        try:
            Account.objects.get(user_id=encoding_cookies.get('id'))
            return False
        except Account.DoesNotExist:
            raise AuthenticationFailed('Incorrect data in cookies')

    def has_object_permission(
        self,
        request: Request,
        view: TransactionViewSet | AccountViewSet,
        obj: Transaction | Account
    ) -> bool:
        authorization = request.COOKIES.get('Authorization')
        if authorization is None:
            return True

        return False
