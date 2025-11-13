from django.db import models
from config import settings as setting
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django.utils.text import slugify



class BaseModel(models.Model):
    user_creation = models.ForeignKey(setting.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                      related_name='%(app_label)s_%(class)s_creation')
    date_creation = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    user_updated = models.ForeignKey(setting.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='%(app_label)s_%(class)s_updated')
    date_updated = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        abstract = True


class Cliente(TenantMixin):
    nombre_compania = models.CharField(max_length=150, unique=True)
    email_contacto = models.EmailField(max_length=254, unique=True)
    pais = models.CharField(max_length=100, blank=True, null=True)
    slug_compania = models.SlugField(max_length=160, unique=True, editable=False)
    trial_starts_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField()
    activo = models.BooleanField(default=True)

    auto_create_schema = True  # crea el schema al guardar

    def save(self, *args, **kwargs):
        if not self.slug_compania:
            base = slugify(self.nombre_compania)
            self.slug_compania = base
        super().save(*args, **kwargs)  # crea schema si no existe

class Dominio(DomainMixin):
    pass