# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0002_auto_20151211_1501'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='type',
            field=models.CharField(default=b'Manual', max_length=128, verbose_name='The type of ledger', choices=[(b'Automatic', b'Automatic'), (b'Manual', b'Manual'), (b'Reconciliation', b'Reconciliation')]),
        ),
        migrations.AlterField(
            model_name='ledgerentry',
            name='amount',
            field=models.DecimalField(verbose_name='Amount of this entry.', max_digits=24, decimal_places=4),
        ),
    ]
