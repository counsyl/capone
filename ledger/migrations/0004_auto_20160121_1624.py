# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0003_auto_20151218_1318'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ledger',
            name='increased_by_debits',
            field=models.BooleanField(default=None, help_text=b'All accounts (and their corresponding ledgers) are of one of two types: either debits increase the value of an account or credits do.  By convention, asset and expense accounts are of the former type, while liabilities, equity, and revenue are of the latter.'),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='type',
            field=models.CharField(default=b'Manual', max_length=128, verbose_name='The type of transaction.  AUTOMATIC is for recurring tasks, and RECONCILIATION is for special Reconciliation transactions.', choices=[(b'Automatic', b'Automatic'), (b'Manual', b'Manual'), (b'Reconciliation', b'Reconciliation')]),
        ),
    ]
