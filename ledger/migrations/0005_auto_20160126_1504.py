# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0004_auto_20160121_1624'),
    ]

    operations = [
        migrations.RenameField(
            model_name='invoicegenerationrecord',
            old_name='_creation_timestamp',
            new_name='creation_timestamp',
        ),
        migrations.RenameField(
            model_name='invoicegenerationrecord',
            old_name='_invoice_timestamp',
            new_name='invoice_timestamp',
        ),
        migrations.RenameField(
            model_name='transaction',
            old_name='_creation_timestamp',
            new_name='creation_timestamp',
        ),
        migrations.RenameField(
            model_name='transaction',
            old_name='_posted_timestamp',
            new_name='posted_timestamp',
        ),
    ]
