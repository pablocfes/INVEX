from django.urls import path
from . import views

app_name = "subscriptions"

urlpatterns = [
    path("billing/", views.billing_home, name="billing_home"),
    path("billing/dummy-pay/", views.billing_dummy_pay, name="billing_dummy_pay"),
]
