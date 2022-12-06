from django.urls import path, include
from rest_framework.routers import DefaultRouter

from bank import views

router = DefaultRouter()
router.register(
    r'transactions', views.TransactionViewSet, basename="transaction"
)
router.register(r'accounts', views.AccountViewSet, basename="account")

urlpatterns = [
    path('', include(router.urls)),
]
