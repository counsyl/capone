# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0003_auto_20151216_1544'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ledger',
            name='are_debits_positive',
        ),
        migrations.AddField(
            model_name='ledger',
            name='increased_by_debits',
            field=models.BooleanField(default=True, help_text=b'All accounts (and their corresponding ledgers) are of one of two types: either debits increase the value of an account or credits do.  By convention, asset and expense accounts are of the former type, while liabilities, equity, and revenue are of the latter.'),
            preserve_default=False,
        ),
    ]
