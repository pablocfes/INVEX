from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django_tenants.utils import schema_context

from .models import Subscription


class SubscriptionAccessMiddleware:
    """
    Protege rutas del tenant.
    - Si la suscripción no permite acceso, redirige a billing.
    - Billing debe estar accesible sin caer en loop.
    """

    ALLOW_PATH_PREFIXES = (
        "/billing",         # pantallas de pago
        "/admin/login",     # opcional
        "/static/",         # estáticos
        "/media/",          # media
        "/health",          # healthcheck opcional
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si no hay tenant en el request, es public: no bloqueamos.
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return self.get_response(request)

        path = request.path or "/"
        if any(path.startswith(p) for p in self.ALLOW_PATH_PREFIXES):
            return self.get_response(request)

        # Buscar suscripción en public
        with schema_context("public"):
            sub = Subscription.objects.filter(tenant=tenant).select_related("tenant").first()

            # Si por alguna razón no existe, lo tratamos como bloqueado
            if not sub:
                return HttpResponseRedirect(self._billing_url(request))

            # opcional: refrescar estado si venció (en caliente)
            changed = sub.refresh_status_if_expired(at=timezone.now())
            if changed:
                sub.save(update_fields=["status", "updated_at"])

            if not sub.is_access_allowed():
                return HttpResponseRedirect(self._billing_url(request))

        return self.get_response(request)

    def _billing_url(self, request) -> str:
        # Idealmente billing está en el mismo dominio del tenant o en dominio principal.
        # Si quieres que sea en dominio principal, aquí construirías la URL absoluta.
        try:
            return reverse("subscriptions:billing_home")
        except Exception:
            return "/billing/"
