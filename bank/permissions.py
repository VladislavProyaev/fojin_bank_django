from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.viewsets import ViewSetMixin

from common.endpoints import EndPoints
from services import rabbit_mq


class IsOwnerOrReadOnly(permissions.BasePermission):

    @rabbit_mq.query(EndPoints.GET_USER)
    def has_permission(
        self, request: Request, view: type[ViewSetMixin], **kwargs
    ) -> bool:
        return rabbit_mq.validate_action(request, view, **kwargs)
