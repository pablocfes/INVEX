from django.views.generic import TemplateView
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django_tenants.utils import tenant_context
from core.models import Cliente, Dominio
from core.forms_public import RegisterTenantForm
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin


class LandingView(TemplateView):
    template_name = "public/landing.html"


def build_unique_slug(base: str) -> str:
    """
    Genera un slug único para schema_name y subdominio.
    Evita colisiones acme, acme-2, etc.
    """
    slug = slugify(base) or "empresa"
    original = slug
    i = 2
    while Cliente.objects.filter(schema_name=slug).exists():
        slug = f"{original}-{i}"
        i += 1
    return slug


from core.seed import run_initial_tenant_seed  # <--- nuevo import

class RegisterTenantView(View):
    template_name = "public/register.html"

    def get(self, request):
        form = RegisterTenantForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = RegisterTenantForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        full_name = form.cleaned_data.get("full_name") or ""
        company_name = form.cleaned_data["company_name"]
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password1"]

        # 1) slug/schema único
        schema = build_unique_slug(company_name)

        # 2) crear tenant (schema)
        cliente = Cliente.objects.create(
            schema_name=schema,
            nombre_compania=company_name,
            trial_ends_at=timezone.now() + timedelta(days=30),
            email_contacto=email,
        )

        # 3) dominio primario
        if settings.MAIN_DOMAIN == "localhost":
            domain = f"{schema}.localhost"
        else:
            domain = f"{schema}.{settings.MAIN_DOMAIN}"

        Dominio.objects.create(
            domain=domain,
            tenant=cliente,
            is_primary=True,
        )

        # 4) crear usuario owner y seed inicial DENTRO del tenant
        with tenant_context(cliente):
            User = get_user_model()
            username = email.split("@")[0]

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "is_active": True,
                    "is_staff": True,
                    "is_superuser": True,  # luego lo puedes bajar a "Owner"
                },
            )
            if created:
                user.set_password(password)
                user.save()

            # 👉 AQUÍ se ejecuta el script inicial
            run_initial_tenant_seed(user=user)

        # 5) redirigir al login del subdominio recién creado
        if settings.MAIN_DOMAIN == "localhost":
            port = f":{request.get_port()}" if request.get_port() not in ("80", "443") else ""
            login_url = f"http://{domain}{port}/login/"
        else:
            login_url = f"https://{domain}/login/"

        messages.success(
            request,
            f"Tu espacio para {company_name} ha sido creado. Ingresa con tus credenciales."
        )
        return redirect(login_url)
