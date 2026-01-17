from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django_tenants.utils import schema_context

import stripe
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django_tenants.utils import schema_context

from core.models import Cliente  # ajusta si tu import real es distinto
from subscriptions.models import Subscription, SubscriptionStatus

# tu helper de auth public
from core.views_public import get_public_user  # ajusta a tu ruta real


from subscriptions.services import mark_subscription_paid_dummy
from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from subscriptions.models import Subscription, SubscriptionStatus

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def billing_home(request):
    tenant = getattr(request, "tenant", None)

    # Si estás en public sin tenant, podrías mostrar “elige tu compañía” o similar.
    if not tenant:
        return render(request, "subscriptions/billing_public.html", {})

    with schema_context("public"):
        sub = Subscription.objects.filter(tenant=tenant).first()

    return render(request, "subscriptions/billing_home.html", {"subscription": sub, "tenant": tenant})

def billing_dummy_pay(request):
    from core.models import PublicAccount, Cliente
    public_user_id = request.session.get("public_user_id", None)
    public_user = PublicAccount.objects.filter(id=public_user_id).first()
    cliente = Cliente.objects.filter(email_contacto=public_user.email).first() if public_user else None
    tenant = cliente if cliente and cliente.schema_name != "public" else None
    print("Public User en billing_dummy_pay:", public_user)
    if not tenant:
        return redirect("account_home")
    print("Tenant en billing_dummy_pay:", tenant)
    with schema_context("public"):
        sub = Subscription.objects.filter(tenant=tenant).first()
        if not sub:
            return redirect("account_home")

        mark_subscription_paid_dummy(subscription=sub, days=30)

    # vuelve al home del tenant (ajusta a tu ruta real)
    print("Subscription en billing_dummy_pay:", sub)
    return redirect("account_home")


@require_POST
def stripe_create_checkout(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return redirect("account_home")

    success_url = request.build_absolute_uri(reverse("subscriptions:stripe_success"))
    cancel_url = request.build_absolute_uri(reverse("subscriptions:billing_home"))

    with schema_context("public"):
        sub = Subscription.objects.get(tenant=tenant)

        # 1) Customer
        if not sub.stripe_customer_id:
            customer = stripe.Customer.create(
                email=sub.owner_user.email,
                name=getattr(sub.owner_user, "full_name", "") or sub.owner_user.email,
                metadata={"tenant_id": str(tenant.id), "schema": tenant.schema_name},
            )
            sub.stripe_customer_id = customer["id"]
            sub.save(update_fields=["stripe_customer_id"])

        # 2) Checkout Session (subscription)
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=sub.stripe_customer_id,
            line_items=[{"price": settings.STRIPE_PRICE_ID_MONTHLY, "quantity": 1}],
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={"tenant_id": str(tenant.id), "schema": tenant.schema_name},
        )

        sub.stripe_checkout_session_id = session["id"]
        sub.save(update_fields=["stripe_checkout_session_id"])

    return JsonResponse({"url": session["url"]})


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception:
        return HttpResponse(status=400)

    event_type = event["type"]
    data = event["data"]["object"]

    with schema_context("public"):
        if event_type == "checkout.session.completed":
            # Session trae customer y subscription
            customer_id = data.get("customer")
            stripe_sub_id = data.get("subscription")

            sub = Subscription.objects.filter(stripe_customer_id=customer_id).first()
            if sub and stripe_sub_id:
                sub.stripe_subscription_id = stripe_sub_id
                # activa en tu sistema
                sub.status = SubscriptionStatus.ACTIVE
                # opcional: poner period_end desde Stripe (mejor vía invoice/subscription)
                sub.save(update_fields=["stripe_subscription_id", "status", "updated_at"])

        elif event_type == "customer.subscription.deleted":
            stripe_sub_id = data.get("id")
            sub = Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).first()
            if sub:
                sub.status = SubscriptionStatus.CANCELED
                sub.save(update_fields=["status", "updated_at"])

        # invoice.paid / subscription.updated lo usas para sincronizar period_end real
        # (ideal) leer current_period_end desde Stripe y guardarlo

    return HttpResponse(status=200)


def _absolute_public_url(request, path: str) -> str:
    """
    Construye URL absoluta en el dominio principal (public).
    Útil si la vista se llama desde algún subdominio por accidente.
    """
    if settings.MAIN_DOMAIN == "localhost":
        port = f":{request.get_port()}" if request.get_port() not in ("80", "443") else ""
        return f"http://localhost{port}{path}"
    return f"https://{settings.MAIN_DOMAIN}{path}"


@require_http_methods(["GET", "POST"])
@csrf_protect
def public_subscription(request):
    """
    Pantalla pública de suscripción:
    - GET: muestra estado (trial/active/past_due) + CTA de pagar
    - POST: crea Stripe Checkout Session (mode=subscription) y redirige a Stripe
    """
    user = get_public_user(request)
    if not user:
        return redirect("public_login")

    with schema_context("public"):
        company = Cliente.objects.filter(email_contacto=user.email).order_by("id").first()

        if not company:
            messages.info(request, "Primero crea tu compañía para activar el plan.")
            return redirect("account_home")

        subscription = Subscription.objects.filter(tenant=company).first()
        if not subscription:
            # Si por alguna razón no existe, lo mejor es crearlo (pero asumo que lo creas en CreateCompanyView)
            messages.error(request, "No encontramos tu suscripción. Intenta de nuevo o contacta soporte.")
            return redirect("account_home")

        # refrescar estado por vencimientos
        changed = subscription.refresh_status_if_expired(at=timezone.now())
        if changed:
            subscription.save(update_fields=["status", "updated_at"])

        now = timezone.now()

        # Datos de UI
        plan_name = "Mensual"
        price_cop = subscription.monthly_price_cop or 29900

        trial_end = subscription.trial_end
        period_end = subscription.current_period_end

        needs_payment = False
        days_left = None

        if subscription.status == SubscriptionStatus.TRIAL and trial_end:
            delta = trial_end - now
            days_left = max(delta.days, 0)
            needs_payment = now > trial_end

        elif subscription.status == SubscriptionStatus.ACTIVE and period_end:
            delta = period_end - now
            days_left = max(delta.days, 0)
            needs_payment = now > period_end

        elif subscription.status in (SubscriptionStatus.PAST_DUE, SubscriptionStatus.SUSPENDED):
            needs_payment = True

        # -------- POST: crear checkout session --------
        if request.method == "POST":
            # Si ya está activo y no necesita pago, no creamos checkout
            if not needs_payment and subscription.status == SubscriptionStatus.ACTIVE:
                messages.info(request, "Tu plan ya está activo ✅")
                return redirect("account_home")

            # 1) Crear/asegurar Stripe Customer
            if not subscription.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=getattr(user, "full_name", "") or user.email,
                    metadata={
                        "tenant_id": str(company.id),
                        "schema_name": company.schema_name,
                    },
                )
                subscription.stripe_customer_id = customer["id"]
                subscription.save(update_fields=["stripe_customer_id"])

            # 2) Crear Checkout Session (subscription)
            success_path = reverse("stripe_success")
            cancel_path = reverse("stripe_cancel")

            success_url = _absolute_public_url(request, success_path) + "?session_id={CHECKOUT_SESSION_ID}"
            cancel_url = _absolute_public_url(request, cancel_path)

            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=subscription.stripe_customer_id,
                line_items=[{"price": settings.STRIPE_PRICE_ID_MONTHLY, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "tenant_id": str(company.id),
                    "schema_name": company.schema_name,
                    "subscription_id": str(subscription.id),
                },
                # Opcional: si quieres permitir códigos de promoción
                # allow_promotion_codes=True,
            )

            subscription.stripe_checkout_session_id = session["id"]
            subscription.save(update_fields=["stripe_checkout_session_id"])

            return redirect(session["url"], permanent=False)

    # -------- GET: render --------
    return render(request, "public/subscriptions/subscription.html", {
        "company": company,
        "subscription": subscription,
        "plan_name": plan_name,
        "price_cop": price_cop,
        "needs_payment": needs_payment,
        "days_left": days_left,
        "trial_end": trial_end,
        "period_end": period_end,
    })


def stripe_success(request):
    """
    Página de éxito (UX).
    - Amarra el session_id al Subscription en public.
    - NO es la fuente de verdad para activar (eso lo hace el webhook).
    """
    user = get_public_user(request)
    if not user:
        return redirect("public_login")

    session_id = request.GET.get("session_id")
    if not session_id:
        messages.success(request, "Listo ✅ Estamos confirmando tu suscripción...")
        return redirect("account_home")

    try:
        # Expandimos subscription para poder leer period_end si quieres mostrarlo
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["subscription"],
        )
    except stripe.error.StripeError:
        messages.success(request, "Pago recibido ✅ Estamos confirmando tu suscripción...")
        return redirect("account_home")

    customer_id = session.get("customer")
    stripe_sub = session.get("subscription")  # puede venir expandido o como id string

    # stripe_sub puede ser dict (expand) o string (id)
    stripe_subscription_id = None
    current_period_end = None

    if isinstance(stripe_sub, dict):
        stripe_subscription_id = stripe_sub.get("id")
        # current_period_end viene como unix timestamp (segundos)
        try:
            cpe = stripe_sub.get("items").get("data")[0].get('current_period_end')
        except Exception:
            # current time plus 30 days as fallback
            cpe = int(timezone.now().timestamp()) + 30 * 24 * 3600
        if cpe:
            current_period_end = timezone.datetime.fromtimestamp(cpe, tz=timezone.utc)
    elif isinstance(stripe_sub, str):
        stripe_subscription_id = stripe_sub

    with schema_context("public"):
        # Encontramos la company por email_contacto del user (tu flujo actual)
        company = Cliente.objects.filter(email_contacto=user.email).order_by("id").first()
        if not company:
            messages.success(request, "Pago recibido ✅ Estamos confirmando tu suscripción...")
            return redirect("account_home")

        sub = Subscription.objects.filter(tenant=company).first()
        if not sub:
            messages.success(request, "Pago recibido ✅ Estamos confirmando tu suscripción...")
            return redirect("account_home")

        # Guardamos evidencias del checkout (útil si el webhook se retrasa)
        updates = []
        if session_id and sub.stripe_checkout_session_id != session_id:
            sub.stripe_checkout_session_id = session_id
            updates.append("stripe_checkout_session_id")

        if customer_id and sub.stripe_customer_id != customer_id:
            sub.stripe_customer_id = customer_id
            updates.append("stripe_customer_id")

        if stripe_subscription_id and sub.stripe_subscription_id != stripe_subscription_id:
            sub.stripe_subscription_id = stripe_subscription_id
            updates.append("stripe_subscription_id")

        # OJO: Yo NO pondría ACTIVE aquí, pero sí puedes pre-llenar current_period_end si ya viene expandido.
        # Aun así, el webhook lo va a confirmar.
        if current_period_end and sub.current_period_end != current_period_end:
            sub.current_period_end = current_period_end
            updates.append("current_period_end")

        if updates:
            sub.save(update_fields=updates + ["updated_at"])

    sub.status = SubscriptionStatus.ACTIVE
    sub.save(update_fields=["status", "updated_at"])
    # Mensaje UX
    messages.success(
        request,
        "Pago completado ✅ Estamos confirmando tu suscripción (esto puede tardar unos segundos)."
    )
    return redirect("account_home")


def stripe_cancel(request):
    user = get_public_user(request)
    if not user:
        return redirect("public_login")

    # opcional: guardar el session_id cancelado (si lo mandas en cancel_url)
    session_id = request.GET.get("session_id")

    # Si quieres registrar el intento, podrías guardar stripe_checkout_session_id igual que arriba
    if session_id:
        with schema_context("public"):
            company = Cliente.objects.filter(email_contacto=user.email).order_by("id").first()
            if company:
                sub = Subscription.objects.filter(tenant=company).first()
                if sub and not sub.stripe_checkout_session_id:
                    sub.stripe_checkout_session_id = session_id
                    sub.save(update_fields=["stripe_checkout_session_id", "updated_at"])

    messages.info(request, "Pago cancelado. Si fue un error, puedes intentarlo de nuevo.")
    return redirect("public_subscription")