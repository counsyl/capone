# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledger',
            name='are_debits_positive',
            field=models.BooleanField(default=True, help_text=b'All accounts (and their corresponding ledgers) are of one of two types: either debits are positive and credits negative, or debits are negative and credits are positive.  By convention, asset and expense accounts are of the former type, while liabilities, equity, and revenue are of the latter.'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='ledger',
            name='entity_content_type',
            field=models.ForeignKey(blank=True, to='contenttypes.ContentType', null=True),
        ),
        migrations.AlterField(
            model_name='ledger',
            name='entity_id',
            field=models.PositiveIntegerField(db_index=True, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='ledger',
            name='type',
            field=models.CharField(blank=True, max_length=128, verbose_name='The ledger type, eg Accounts Receivable, Revenue, etc', choices=[(b'ar', b'Accounts Receivable'), (b'revenue', b'Revenue'), (b'cash', b'Cash')]),
        ),
    ]
