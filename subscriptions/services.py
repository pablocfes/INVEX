from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context

from .models import Subscription, SubscriptionStatus, Payment, PaymentProvider, PaymentStatus


@transaction.atomic
def create_trial_subscription_for_tenant(*, tenant, owner_user, trial_days: int = 30) -> Subscription:
    """
    Crea suscripción TRIAL en public. Debe llamarse justo cuando creas el tenant.
    """
    with schema_context("public"):
        sub, created = Subscription.objects.get_or_create(
            tenant=tenant,
            defaults={
                "owner_user": owner_user,
                "monthly_price_cop": 29900,
            },
        )
        if created or sub.status == SubscriptionStatus.CANCELED:
            sub.owner_user = owner_user
            sub.start_trial(days=trial_days)
            sub.save()
        return sub


@transaction.atomic
def mark_subscription_paid_dummy(*, subscription: Subscription, days: int = 30) -> Payment:
    """
    Simula un pago exitoso y activa la suscripción por X días.
    """
    now = timezone.now()
    with schema_context("public"):
        subscription.refresh_from_db()

        pay = Payment.objects.create(
            subscription=subscription,
            amount_cop=subscription.monthly_price_cop,
            provider=PaymentProvider.DUMMY,
            status=PaymentStatus.SUCCEEDED,
            reference=Payment.new_reference(),
        )

        subscription.activate_for_days(days=days)
        subscription.last_payment_at = now
        subscription.last_payment_ref = pay.reference
        subscription.save()

        return pay
