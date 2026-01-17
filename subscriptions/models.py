import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class SubscriptionStatus(models.TextChoices):
    TRIAL = "TRIAL", "En Prueba"
    ACTIVE = "ACTIVE", "Activo"
    PAST_DUE = "PAST_DUE", "Vencido"
    SUSPENDED = "SUSPENDED", "Suspendido"
    CANCELED = "CANCELED", "Cancelado"


class PaymentStatus(models.TextChoices):
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"
    PENDING = "PENDING", "Pending"


class PaymentProvider(models.TextChoices):
    DUMMY = "DUMMY", "Dummy"
    STRIPE = "STRIPE", "Stripe"


class Subscription(models.Model):
    # Ajusta el import según tu tenant model real
    # Si tu tenant está en app "customers" o "core", cambia "core.Cliente"
    tenant = models.OneToOneField("core.Cliente", on_delete=models.CASCADE, related_name="subscription")

    owner_user = models.ForeignKey(
        "core.PublicAccount",
        on_delete=models.PROTECT,
        related_name="owned_subscriptions",
    )

    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.TRIAL)

    stripe_customer_id = models.CharField(max_length=120, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, null=True, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=120, null=True, blank=True)
    stripe_price_id = models.CharField(max_length=120, null=True, blank=True)
    monthly_price_cop = models.PositiveIntegerField(default=29900)

    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    grace_end = models.DateTimeField(null=True, blank=True)

    last_payment_at = models.DateTimeField(null=True, blank=True)
    last_payment_ref = models.CharField(max_length=120, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def start_trial(self, days: int = 30):
        now = timezone.now()
        self.status = SubscriptionStatus.TRIAL
        self.trial_start = now
        self.trial_end = now + timedelta(days=days)
        self.grace_end = None
        return self

    def activate_for_days(self, days: int = 30):
        now = timezone.now()
        self.status = SubscriptionStatus.ACTIVE
        self.current_period_start = now
        self.current_period_end = now + timedelta(days=days)
        self.grace_end = None
        return self

    def is_access_allowed(self, at=None) -> bool:
        at = at or timezone.now()

        if self.status == SubscriptionStatus.TRIAL:
            return bool(self.trial_end and at <= self.trial_end)

        if self.status == SubscriptionStatus.ACTIVE:
            return bool(self.current_period_end and at <= self.current_period_end)

        if self.status == SubscriptionStatus.PAST_DUE:
            # si usas gracia
            return bool(self.grace_end and at <= self.grace_end)

        return False

    def refresh_status_if_expired(self, at=None) -> bool:
        """
        Actualiza estado si se venció trial/periodo.
        Retorna True si cambió algo.
        """
        at = at or timezone.now()
        changed = False

        if self.status == SubscriptionStatus.TRIAL and self.trial_end and at > self.trial_end:
            self.status = SubscriptionStatus.PAST_DUE
            changed = True

        if self.status == SubscriptionStatus.ACTIVE and self.current_period_end and at > self.current_period_end:
            self.status = SubscriptionStatus.PAST_DUE
            changed = True

        return changed

    def __str__(self):
        return f"Subscription({self.tenant_id}) - {self.status}"


class Payment(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="payments")
    amount_cop = models.PositiveIntegerField()
    provider = models.CharField(max_length=20, choices=PaymentProvider.choices, default=PaymentProvider.DUMMY)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.SUCCEEDED)

    reference = models.CharField(max_length=120, default="", blank=True)
    raw_data = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def new_reference() -> str:
        return str(uuid.uuid4())

    def __str__(self):
        return f"Payment({self.provider}) {self.amount_cop} {self.status}"
