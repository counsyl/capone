# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0002_auto_20151216_1914'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='amount',
            field=models.DecimalField(default=Decimal('0'), max_digits=24, decimal_places=4),
        ),
    ]
