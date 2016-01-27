# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0005_auto_20160126_1504'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ledger',
            name='transactions',
        ),
        migrations.AlterField(
            model_name='invoicegenerationrecord',
            name='creation_timestamp',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Time this invoice was generated', db_index=True),
        ),
        migrations.AlterField(
            model_name='invoicegenerationrecord',
            name='invoice_timestamp',
            field=models.DateTimeField(verbose_name='Time of the Invoice', db_index=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='creation_timestamp',
            field=models.DateTimeField(help_text='Time this transaction was recorded locally.  This field should *always* equal when this object was created.', auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='posted_timestamp',
            field=models.DateTimeField(help_text='Time the transaction was posted.  Change this field to model retroactive ledger entries.', db_index=True),
        ),
    ]
