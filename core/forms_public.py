from django import forms
from core.models import Cliente
from django import forms
from django.contrib.auth.forms import UserCreationForm
import re


class RegisterTenantForm(forms.Form):
    full_name = forms.CharField(
        label="Tu nombre",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu nombre completo',
            'minlength': '2',
            'maxlength': '150'
        })
    )
    company_name = forms.CharField(
        label="Nombre de la compañía",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre de tu compañía',
            'minlength': '2',
            'maxlength': '150'
        })
    )
    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu@ejemplo.com',
            'pattern': '[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}$'
        })
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña segura',
            'minlength': '8',
            'pattern': '^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[@$!%*?&])[A-Za-z\\d@$!%*?&]{8,}$'
        }),
        required=True,
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite tu contraseña',
            'minlength': '8'
        }),
        required=True,
    )

    def clean_company_name(self):
        company_name = self.cleaned_data.get("company_name")
        if Cliente.objects.filter(nombre_compania=company_name).exists():
            raise forms.ValidationError("Ya existe una compañía con este nombre, por favor ingrese otro nombre.")

        if len(company_name) < 2:
            raise forms.ValidationError("El nombre de la compañía debe tener al menos 2 caracteres.")

        # Validar que solo contenga caracteres permitidos
        if not re.match(r'^[a-zA-Z0-9\sáéíóúÁÉÍÓÚñÑ\-\.]+$', company_name):
            raise forms.ValidationError("El nombre de la compañía contiene caracteres no válidos.")

        return company_name

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name")
        if full_name and len(full_name) < 2:
            raise forms.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return full_name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if Cliente.objects.filter(email_contacto=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if password1:
            if len(password1) < 8:
                raise forms.ValidationError("La contraseña debe tener al menos 8 caracteres.")

            # Validar fortaleza de contraseña
            if not re.search(r'[A-Z]', password1):
                raise forms.ValidationError("La contraseña debe contener al menos una letra mayúscula.")

            if not re.search(r'[a-z]', password1):
                raise forms.ValidationError("La contraseña debe contener al menos una letra minúscula.")

            if not re.search(r'\d', password1):
                raise forms.ValidationError("La contraseña debe contener al menos un número.")

            if not re.search(r'[@$!%*?&]', password1):
                raise forms.ValidationError("La contraseña debe contener al menos un carácter especial (@$!%*?&).")

        return password1

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")

        return cleaned
    
