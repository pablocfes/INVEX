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
from core.models import Cliente, Dominio, PublicAccount
from core.forms_public import RegisterTenantForm, RegisterUserForm, CompanyForm, PublicLoginForm
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from core.auth_public import hash_password, verify_password
from subscriptions.services import create_trial_subscription_for_tenant
from django.urls import reverse
 
from django_tenants.utils import tenant_context, schema_context


from django_tenants.utils import schema_context

from subscriptions.models import Subscription, SubscriptionStatus


class LandingView(TemplateView):
    template_name = "public/landing.html"

    def dispatch(self, request, *args, **kwargs):

        if request.session.get("signup_full_name"):
            return redirect("account_home")
        return super().dispatch(request, *args, **kwargs)
    


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


class RegisterUserView(View):
    template_name = "public/register.html"

    def get(self, request):
        form = RegisterUserForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = RegisterUserForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        full_name = form.cleaned_data.get("full_name") or ""
        email = form.cleaned_data["email"].lower().strip()
        password = form.cleaned_data["password1"]

        # Crear cuenta pública
        account, created = PublicAccount.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "password_hash": hash_password(password),
            },
        )

        if not created:
            messages.error(request, "Este correo ya está registrado. Inicia sesión.")
            return redirect("public_login")

        # Iniciar sesión en portal público
        public_login(request, account)
        return redirect("account_home")


class AccountHomeView(View):
    template_name = "public/account_home.html"

    def get(self, request):
        user = get_public_user(request)
        if not user:
            return redirect("public_login")

        companies = Cliente.objects.filter(email_contacto=user.email).order_by("id")
        company = companies.first()

        space_url = None
        if company:
            if settings.MAIN_DOMAIN == "localhost":
                port = f":{request.get_port()}" if request.get_port() not in ("80", "443") else ""
                domain = f"{company.schema_name}.localhost"
                space_url = f"http://{domain}{port}/"
            else:
                domain = f"{company.schema_name}.{settings.MAIN_DOMAIN}"
                space_url = f"https://{domain}/"

        # ====== SUSCRIPCIÓN ======
        subscription = None
        plan_label = "Trial"
        price_label = "$29.900"
        days_left = None
        needs_payment = False
        trial_end = None
        period_end = None
        stripe_ready = False

        billing_url = reverse("public_subscription")  # tu pantalla en public

        if company:
            with schema_context("public"):
                subscription = Subscription.objects.filter(tenant=company).first()

                if subscription:
                    # refrescar estado si venció
                    changed = subscription.refresh_status_if_expired(at=timezone.now())
                    if changed:
                        subscription.save(update_fields=["status", "updated_at"])

                    now = timezone.now()
                    plan_label = subscription.status
                    trial_end = subscription.trial_end
                    period_end = subscription.current_period_end

                    stripe_ready = bool(subscription.stripe_customer_id or subscription.stripe_subscription_id)

                    if subscription.status == SubscriptionStatus.TRIAL and subscription.trial_end:
                        delta = subscription.trial_end - now
                        days_left = max(delta.days, 0)
                        needs_payment = now > subscription.trial_end
                        print("DAYS LEFT TRIAL:", days_left)

                    elif subscription.status == SubscriptionStatus.ACTIVE and subscription.current_period_end:
                        delta = subscription.current_period_end - now
                        days_left = max(delta.days, 0)
                        needs_payment = now > subscription.current_period_end
                        print("DAYS LEFT ACTIVE:", days_left)

                    elif subscription.status in (SubscriptionStatus.PAST_DUE, SubscriptionStatus.SUSPENDED):
                        needs_payment = True
                        print("NEEDS PAYMENT DUE/SUSPENDED")

        return render(request, self.template_name, {
            "full_name": user.full_name,
            "email": user.email,
            "company": company,
            "space_url": space_url,

            "subscription": subscription,
            "plan_label": plan_label,
            "price_label": price_label,
            "days_left": days_left,
            "needs_payment": needs_payment,
            "trial_end": trial_end,
            "period_end": period_end,
            "billing_url": billing_url,
            "stripe_ready": stripe_ready,
        })


class CreateCompanyView(View):
    template_name = "public/create_company.html"

    def get(self, request):
        user = get_public_user(request)
        if not user:
            return redirect("public_login")

        if Cliente.objects.filter(email_contacto=user.email).exists():
            return redirect("account_home")

        return render(request, self.template_name, {"form": CompanyForm()})

    def post(self, request):
        public_user = get_public_user(request)
        if not public_user:
            return redirect("public_login")

        email = public_user.email

        form = CompanyForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        company_name = form.cleaned_data["company_name"]
        password = form.cleaned_data["password"]

        # Evitar duplicados por email_contacto
        if Cliente.objects.filter(email_contacto=email).exists():
            messages.info(request, "Ya tienes una compañía asociada a este correo.")
            return redirect("account_home")

        # 1) slug/schema único
        schema = build_unique_slug(company_name)

        # 2) crear tenant (schema)
        #    Puedes dejar trial_ends_at por compatibilidad, pero la lógica real vivirá en Subscription
        cliente = Cliente.objects.create(
            schema_name=schema,
            nombre_compania=company_name,
            trial_ends_at=timezone.now() + timedelta(days=30),  # opcional/legacy
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

        # 4) crear suscripción TRIAL en PUBLIC (fuente de verdad)
        #    (esto garantiza que AccountHome y middleware puedan validar estado)
        create_trial_subscription_for_tenant(
            tenant=cliente,
            owner_user=public_user,   # user en public
            trial_days=30,
        )

        # 5) crear usuario owner + seed dentro del tenant
        with tenant_context(cliente):
            User = get_user_model()
            username = email

            tenant_user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "names": public_user.full_name,
                    "username": username,
                    "is_active": True,
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            if created:
                tenant_user.set_password(password)
                tenant_user.save()

            run_initial_tenant_seed(user=tenant_user, company_info=form.cleaned_data)

        messages.success(
            request,
            f"Tu compañía {company_name} ha sido creada. Tienes 30 días de prueba gratis 🎉"
        )
        return redirect("account_home")


class PublicLoginView(View):
    template_name = "public/login_public.html"

    def get(self, request):
        if get_public_user(request):
            return redirect("account_home")
        return render(request, self.template_name, {"form": PublicLoginForm()})

    def post(self, request):
        form = PublicLoginForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        email = form.cleaned_data["email"].lower().strip()
        password = form.cleaned_data["password"]

        account = PublicAccount.objects.filter(email=email, is_active=True).first()
        if not account or not verify_password(password, account.password_hash):
            messages.error(request, "Credenciales inválidas.")
            return render(request, self.template_name, {"form": form})

        public_login(request, account)
        return redirect("account_home")


class PublicLogoutView(View):
    def post(self, request):
        public_logout(request)
        return redirect("landing")


def public_login(request, account: PublicAccount):
    request.session["public_user_id"] = account.id
    request.session.modified = True
    account.last_login = timezone.now()
    account.save(update_fields=["last_login"])

def public_logout(request):
    request.session.pop("public_user_id", None)
    request.session.modified = True

def get_public_user(request):
    uid = request.session.get("public_user_id")
    if not uid:
        return None
    return PublicAccount.objects.filter(id=uid, is_active=True).first()