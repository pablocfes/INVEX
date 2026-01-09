from django.urls import path
from core import views_public

urlpatterns = [
    path("", views_public.LandingView.as_view(), name="landing"),
    path("registro/", views_public.RegisterUserView.as_view(), name="registro"),
    path("mi-cuenta/", views_public.AccountHomeView.as_view(), name="account_home"),
    path("mi-cuenta/crear-compania/", views_public.CreateCompanyView.as_view(), name="create_company"),
    path("login/", views_public.PublicLoginView.as_view(), name="public_login"),
    path("logout/", views_public.PublicLogoutView.as_view(), name="public_logout"),
]
