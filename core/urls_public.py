from django.urls import path
from core.views_public import LandingView, RegisterTenantView

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("registro/", RegisterTenantView.as_view(), name="registro"),
]
