import json
import uuid
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Any

import pika
from pika.adapters.blocking_connection import BlockingChannel
from rest_framework import viewsets
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from common.actions import PermissionActions
from common.endpoints import EndPoints
from common.methods import HTTPMethods


@dataclass(slots=True)
class RabbitMQMethod:
    method_name: str
    method_function: Callable


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
                view: type[viewsets.ViewSet],
                request: Request,
                *args,
                **kwargs
            ) -> Any:
                body = json.dumps(request.data.copy()).encode('utf-8')
                properties = self.build_properties()
                self.publish_message(body, properties, routing_key=routing_key)

                for method, _, body in self.channel.consume(self.__queue_name):
                    self.channel.basic_ack(method.delivery_tag)
                    answer, status = self.handle_delivery(body)
                    self.channel.cancel()

                    if status:
                        return function(view, request, **answer)
                    else:
                        raise APIException(answer)

            return make_query

        return decorator

    @staticmethod
    def get_action(request: Request, *args) -> str:
        # TODO
        from bank.views import AccountViewSet, TransactionViewSet

        method = request.method
        view = args[0]

        # TODO Complete exceptions
        if isinstance(view, AccountViewSet):
            if method == HTTPMethods.GET:
                if request.parser_context.get('kwargs'):
                    return PermissionActions.VIEW_PROFILE
                return PermissionActions.VIEW_ALL_PROFILES
            elif method == HTTPMethods.POST:
                return PermissionActions.CREATE_ACCOUNT
            elif method == HTTPMethods.PUT:
                return PermissionActions.ASSIGN_ADMINISTRATOR
            else:
                raise APIException(code=404)
        elif isinstance(view, TransactionViewSet):
            if method == HTTPMethods.GET:
                return PermissionActions.VIEW_ALL_PROFILES
            elif method == HTTPMethods.POST:
                return PermissionActions.CREATE_TRANSFER
            else:
                raise APIException(code=404)
        else:
            raise APIException(code=404)

    def validate_action(self) -> Callable:
        def decorator(function: Callable) -> Callable:
            @wraps(function)
            def make_query(
                permission: type[BasePermission],
                request: Request,
                *args,
                **kwargs
            ) -> Any:
                action = self.get_action(request, *args)
                body = json.dumps({'action': action}).encode('utf-8')
                unique_message_id = self.unique_message_id
                properties = self.build_properties(
                    request.COOKIES, unique_message_id
                )
                self.publish_message(
                    body, properties, EndPoints.VALIDATE_ACTION
                )

                answer = self.get_answer(unique_message_id)
                kwargs['available'] = answer
                print('---------------------------------------------')
                print(request.method, action, answer)
                print('---------------------------------------------')
                return function(permission, request, *args, **kwargs)

            return make_query

        return decorator

    def get_answer(self, unique_message_id: str):
        for method, _, body in self.channel.consume(self.__queue_name):
            self.channel.basic_ack(method.delivery_tag)
            answer, status, message_id = self.handle_delivery(body)
            if not status:
                raise APIException(code=404, detail=str(answer))
            self.channel.cancel()
            if message_id != unique_message_id:
                self.get_answer(message_id)

            return answer

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
