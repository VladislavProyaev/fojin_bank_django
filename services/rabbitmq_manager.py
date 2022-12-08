import json
import uuid
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Any

import pika
from django.contrib.auth.models import Permission
from django.db.models import Q
from pika.adapters.blocking_connection import BlockingChannel
from rest_framework import viewsets
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.viewsets import ViewSetMixin

from bank.models import Account, Transaction
from common.actions import PermissionActions
from common.endpoints import EndPoints
from common.methods import HTTPMethods


@dataclass(slots=True)
class RabbitMQMethod:
    method_name: str
    method_function: Callable


class TokenNotProvided(APIException):
    status_code = 401
    default_detail = 'Token not provided.'
    default_code = 'no_token'


class RabbitError(APIException):
    status_code = 400
    default_detail = 'Something wont wrong. Please try again later.'
    default_code = 'something_wont_wrong'


class RabbitMQ:
    def __init__(self, connection_string: str, channel_number: int) -> None:
        self.parameters = pika.URLParameters(connection_string)
        self.__channel_number = channel_number
        self.__queue_name = 'bank_django_service'
        self.__answers = {}

        self.__connection: pika.BlockingConnection | None = None
        self.__channel: BlockingChannel | None = None

    def query(self, routing_key: str) -> Callable:
        def decorator(function: Callable) -> Callable:
            @wraps(function)
            def make_query(
                instance: type[viewsets.ViewSet] | type[Permission],
                request: Request,
                *args,
                **kwargs
            ) -> Any:
                try:
                    headers = {
                        'Authorization': request.META['HTTP_AUTHORIZATION']
                    }
                except KeyError:
                    raise TokenNotProvided()
                is_super_permission = self.is_super_permission(request)
                body = json.dumps(request.data.copy()).encode('utf-8')
                properties = self.build_properties(headers=headers)
                self.publish_message(body, properties, routing_key=routing_key)

                for method, _, body in self.channel.consume(self.__queue_name):
                    self.channel.basic_ack(method.delivery_tag)
                    answer, status, _ = self.handle_delivery(body)
                    self.channel.cancel()
                    answer['is_super_permission'] = is_super_permission

                    if status:
                        return function(instance, request, *args, **answer)
                    else:
                        raise RabbitError(answer)

            return make_query

        return decorator

    @staticmethod
    def get_action(
        request: Request,
        view: type[ViewSetMixin],
        **kwargs
    ) -> str:
        # TODO
        from bank.views import AccountViewSet, TransactionViewSet

        method = request.method
        is_super_permission = kwargs['is_super_permission']

        # TODO Complete exceptions
        if isinstance(view, AccountViewSet):
            if method == HTTPMethods.GET:
                pk = request.parser_context.get('kwargs').get('pk')
                if pk is not None:
                    if is_super_permission:
                        return PermissionActions.VIEW_PROFILE
                    user_id = kwargs.get('user_id')
                    account = (
                        Account.objects.filter(user_id=user_id, pk=pk).first()
                    )
                    if account is not None:
                        return PermissionActions.VIEW_PROFILE
                    return PermissionActions.VIEW_ALL_PROFILES

                if is_super_permission:
                    return PermissionActions.VIEW_ALL_PROFILES
                return PermissionActions.VIEW_PROFILE
            elif method == HTTPMethods.POST:
                return PermissionActions.CREATE_ACCOUNT
            elif method == HTTPMethods.PUT:
                return PermissionActions.ASSIGN_ADMINISTRATOR
            else:
                raise APIException(code=404)
        elif isinstance(view, TransactionViewSet):
            if method == HTTPMethods.GET:
                pk = request.parser_context.get('kwargs').get('pk')
                if pk is not None:
                    if is_super_permission:
                        return PermissionActions.VIEW_PROFILE
                    user_id = kwargs.get('user_id')
                    transaction = Transaction.objects.filter(
                        Q(sender_id__user_id=user_id)
                        | Q(recipient_id__user_id=user_id),
                        pk=pk
                    ).first()
                    if transaction is not None:
                        return PermissionActions.VIEW_PROFILE
                    return PermissionActions.VIEW_ALL_PROFILES

                if is_super_permission:
                    return PermissionActions.VIEW_ALL_PROFILES
                return PermissionActions.VIEW_PROFILE
            elif method == HTTPMethods.POST:
                return PermissionActions.CREATE_TRANSFER
            else:
                raise APIException(code=404)
        else:
            raise APIException(code=404)

    def is_super_permission(self, request: Request) -> bool:
        headers = {
            'Authorization': request.META['HTTP_AUTHORIZATION']
        }
        unique_message_id = self.unique_message_id
        properties = self.build_properties(headers, unique_message_id)
        self.publish_message(
            b'', properties, EndPoints.IS_SUPER_PERMISSION
        )

        status, answer = self.get_answer(request, unique_message_id)
        if not status:
            raise APIException(code=404, detail=str(answer))

        return answer

    def validate_action(
        self, request: Request, view: type[ViewSetMixin], **kwargs
    ) -> bool:
        is_super_permission = self.is_super_permission(request)
        if (
            is_super_permission
            and request.method not in [HTTPMethods.GET, HTTPMethods.PUT]
        ):
            return False

        kwargs['is_super_permission'] = is_super_permission
        action = self.get_action(request, view, **kwargs)
        body = json.dumps({'action': action}).encode('utf-8')
        unique_message_id = self.unique_message_id

        headers = {
            'Authorization': request.META['HTTP_AUTHORIZATION']
        }
        properties = self.build_properties(
            headers, unique_message_id
        )
        self.publish_message(
            body, properties, EndPoints.VALIDATE_ACTION
        )

        status, answer = self.get_answer(request, unique_message_id)
        if action == PermissionActions.CREATE_ACCOUNT:
            if not status or not answer:
                raise APIException(code=404, detail=str(answer))

        return answer

    def get_answer(self, request: Request, unique_message_id: str):
        for method, _, body in self.channel.consume(self.__queue_name):
            self.channel.basic_ack(method.delivery_tag)
            answer, status, message_id = self.handle_delivery(body)
            self.channel.cancel()
            if message_id != unique_message_id:
                self.get_answer(request, message_id)

            return status, answer

    @property
    def unique_message_id(self):
        return str(uuid.uuid4())

    def publish_message(
        self,
        body: bytes,
        properties: pika.BasicProperties,
        routing_key: str = None
    ) -> None:
        self.channel.basic_publish(
            exchange='',
            routing_key=routing_key,
            body=body,
            properties=properties,
            mandatory=True
        )

    def build_properties(
        self, headers: dict | None = None, message_id: str | None = None
    ) -> pika.BasicProperties:
        return pika.BasicProperties(
            reply_to=self.__queue_name, headers=headers, message_id=message_id
        )

    @property
    def connection(self) -> pika.BlockingConnection:
        if self.__connection is None:
            self.__connection = pika.BlockingConnection(self.parameters)
        return self.__connection

    @property
    def channel(self) -> BlockingChannel:
        if self.__channel is None:
            self.__channel = self.connection.channel(self.__channel_number)
            self.__channel.queue_declare(
                queue=self.__queue_name
            )
            self.__channel.confirm_delivery()

        return self.__channel

    @staticmethod
    def handle_delivery(body: bytes) -> tuple[str | dict | bool, bool, str]:
        body = json.loads(body.decode('utf-8'))
        answer = body.get('answer')
        status = body.get('status')
        message_id = body.get('message_id')
        return answer, status, message_id
