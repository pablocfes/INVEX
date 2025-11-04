from config import wsgi
import json
import random
import string
from random import randint

from pos.models import *
from security.models import *

numbers = list(string.digits)
letters = list(string.ascii_letters)
alphanumeric = numbers + letters


def insert_products():
    with open(f'{settings.BASE_DIR}/deploy/json/products.json', encoding='utf8') as json_file:
        data = json.load(json_file)
        for i in data['rows'][0:80]:
            row = i['value']
            product = Product()
            product.name = row['nombre']
            product.code = ''.join(random.choices(alphanumeric, k=8)).upper()
            product.description = 's/n'
            product.category = product.get_or_create_category(name=row['marca'])
            product.price = randint(1, 10)
            product.pvp = (float(product.price) * 0.12) + float(product.price)
            product.inventoried = 1
            product.save()
            print(product.name)


def insert_purchase():
    provider = Provider()
    provider.name = 'EXPALSA S.A.'
    provider.nit = ''.join(random.choices(numbers, k=13))
    provider.email = 'expalsa@gmail.com'
    provider.mobile = ''.join(random.choices(numbers, k=10))
    provider.address = 'Duran'
    provider.save()

    for i in range(1, 5):
        purchase = Purchase()
        purchase.number = ''.join(random.choices(numbers, k=8))
        purchase.provider_id = 1
        purchase.save()

        for d in range(1, 20):
            purchasedetail = PurchaseDetail()
            purchasedetail.purchase_id = purchase.id
            purchasedetail.product_id = randint(1, Product.objects.all().count())
            while purchase.purchasedetail_set.filter(product_id=purchasedetail.product_id).exists():
                purchasedetail.product_id = randint(1, Product.objects.all().count())
            purchasedetail.cant = randint(1, 50)
            purchasedetail.price = purchasedetail.product.pvp
            purchasedetail.subtotal = float(purchasedetail.price) * purchasedetail.cant
            purchasedetail.save()
            purchasedetail.product.stock += purchasedetail.cant
            purchasedetail.product.save()

        purchase.calculate_invoice()
        print(i)


def insert_sale():
    user = User()
    user.names = 'Ana Gabriela Matute Guamán'
    user.dni = ''.join(random.choices(numbers, k=10))
    user.email = 'gabrielamatuteg1@gmail.com'
    user.username = user.dni
    user.set_password(user.dni)
    user.save()
    user.groups.add(Group.objects.get(pk=settings.GROUPS.get('client')))
    client = Client()
    client.user = user
    client.mobile = ''.join(random.choices(numbers, k=10))
    client.address = 'Milagro'
    client.save()
    for i in range(1, 11):
        sale = Sale()
        sale.employee_id = 1
        sale.client_id = 1
        sale.iva = 0.12
        sale.save()
        for d in range(1, 8):
            numberList = list(Product.objects.filter(stock__gt=0).values_list(flat=True))
            saledetail = SaleDetail()
            saledetail.sale_id = sale.id
            saledetail.product_id = random.choice(numberList)
            while sale.saledetail_set.filter(product_id=saledetail.product_id).exists():
                saledetail.product_id = random.choice(numberList)
            saledetail.cant = randint(1, saledetail.product.stock)
            saledetail.price = saledetail.product.pvp
            saledetail.subtotal = float(saledetail.price) * saledetail.cant
            saledetail.save()
            saledetail.product.stock -= saledetail.cant
            saledetail.product.save()

        sale.calculate_invoice()
        sale.cash = sale.total
        sale.save()
        print(i)


insert_products()
insert_purchase()
insert_sale()
