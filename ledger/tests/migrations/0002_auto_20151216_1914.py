# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='creditcardtransaction',
            name='amount',
            field=models.DecimalField(default=0, max_digits=24, decimal_places=4),
        ),
        migrations.AddField(
            model_name='creditcardtransaction',
            name='datetime',
            field=models.DateTimeField(default=datetime.datetime(2015, 12, 16, 19, 14, 27, 915066), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='amount',
            field=models.DecimalField(default=0, max_digits=24, decimal_places=4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='datetime',
            field=models.DateTimeField(default=datetime.datetime(2015, 12, 16, 19, 14, 48, 267106), auto_now_add=True),
            preserve_default=False,
        ),
    ]
