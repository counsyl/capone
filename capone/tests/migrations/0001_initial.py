# -*- coding: utf-8 -*-

from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CreditCardTransaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('cardholder_name', models.CharField(max_length=255)),
                ('datetime', models.DateTimeField(auto_now_add=True)),
                ('amount', models.DecimalField(default=Decimal('0'), max_digits=24, decimal_places=4)),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('patient_name', models.CharField(max_length=255)),
                ('datetime', models.DateTimeField(auto_now_add=True)),
                ('amount', models.DecimalField(default=Decimal('0'), max_digits=24, decimal_places=4)),
                ('barcode', models.CharField(unique=True, max_length=255)),
            ],
        ),
    ]
