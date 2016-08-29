# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0006_auto_20160126_2224'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='ledgerentry',
            options={'verbose_name_plural': 'ledger entries'},
        ),
        migrations.RemoveField(
            model_name='transaction',
            name='finalized',
        ),
        migrations.AddField(
            model_name='ledger',
            name='description',
            field=models.TextField(help_text='Any notes to go along with this Transaction.', blank=True),
        ),
        migrations.AlterField(
            model_name='invoicegenerationrecord',
            name='amount',
            field=models.DecimalField(help_text='Amount for this entry.  Debits are positive, and credits are negative.', max_digits=24, decimal_places=4),
        ),
        migrations.AlterField(
            model_name='invoicegenerationrecord',
            name='creation_timestamp',
            field=models.DateTimeField(help_text='Time this invoice was generated', auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='invoicegenerationrecord',
            name='invoice_timestamp',
            field=models.DateTimeField(help_text='Time of the Invoice', db_index=True),
        ),
        migrations.AlterField(
            model_name='ledger',
            name='name',
            field=models.CharField(help_text='Name of this ledger', unique=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='ledger',
            name='type',
            field=models.CharField(blank=True, help_text='The ledger type, eg Accounts Receivable, Revenue, etc', max_length=128, choices=[(b'ar', b'Accounts Receivable'), (b'revenue', b'Revenue'), (b'cash', b'Cash')]),
        ),
        migrations.AlterField(
            model_name='ledgerentry',
            name='action_type',
            field=models.CharField(help_text='Type of action that created this LedgerEntry', max_length=128, blank=True),
        ),
        migrations.AlterField(
            model_name='ledgerentry',
            name='amount',
            field=models.DecimalField(help_text='Amount for this entry.  Debits are positive, and credits are negative.', max_digits=24, decimal_places=4),
        ),
        migrations.AlterField(
            model_name='ledgerentry',
            name='entry_id',
            field=models.UUIDField(help_text='UUID for this ledger entry', unique=True, max_length=32, editable=False, blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='notes',
            field=models.TextField(help_text='Any notes to go along with this Transaction.', blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transaction_id',
            field=models.UUIDField(help_text='UUID for this transaction', unique=True, max_length=32, editable=False, blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='type',
            field=models.CharField(default=b'Manual', help_text='The type of transaction.  AUTOMATIC is for recurring tasks, and RECONCILIATION is for special Reconciliation transactions.', max_length=128, choices=[(b'Automatic', b'Automatic'), (b'Manual', b'Manual'), (b'Reconciliation', b'Reconciliation')]),
        ),
        migrations.AlterField(
            model_name='transactionrelatedobject',
            name='primary',
            field=models.BooleanField(default=False, help_text='Is this the primary related object?'),
        ),
    ]
