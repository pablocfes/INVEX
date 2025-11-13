from datetime import datetime

from pos.models import Company
from security.models import Dashboard
from django.db import connection
from django.conf import settings

def system_information(request):
    if connection.schema_name == getattr(settings, "PUBLIC_SCHEMA_NAME", "public"):
        return {}

    dashboard = Dashboard.objects.first()
    parameters = {
        'dashboard': dashboard,
        'date_joined': datetime.now(),
        'menu': 'hztbody.html' if dashboard is None else dashboard.get_template_from_layout(),
        'company': Company.objects.first()
    }
    return parameters
