# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0003_auto_20151216_1919'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='barcode',
            field=models.CharField(default=0, unique=True, max_length=255),
            preserve_default=False,
        ),
    ]
