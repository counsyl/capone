# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceGenerationRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('_creation_timestamp', models.DateTimeField(auto_now_add=True, verbose_name='UTC time this invoice was generated', db_index=True)),
                ('_invoice_timestamp', models.DateTimeField(verbose_name='UTC time of the Invoice', db_index=True)),
                ('amount', models.DecimalField(help_text='Money owed to us is positive. Payments out are negative.', verbose_name='Amount of this Invoice.', max_digits=24, decimal_places=4)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Ledger',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=128, verbose_name='The ledger type, eg Accounts Receivable, Revenue, etc', choices=[(b'ar', b'Accounts Receivable'), (b'revenue', b'Revenue'), (b'cash', b'Cash')])),
                ('entity_id', models.PositiveIntegerField(db_index=True)),
                ('name', models.CharField(max_length=255, verbose_name='Name of this ledger')),
                ('entity_content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LedgerEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('entry_id', models.UUIDField(verbose_name='UUID for this ledger entry', unique=True, max_length=32, editable=False, blank=True)),
                ('amount', models.DecimalField(help_text='Debits are positive, credits are negative.', verbose_name='Amount of this entry.', max_digits=24, decimal_places=4)),
                ('action_type', models.CharField(max_length=128, verbose_name='Type of action that created this LedgerEntry', blank=True)),
                ('ledger', models.ForeignKey(related_name='entries', to='ledger.Ledger')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('transaction_id', models.UUIDField(verbose_name='UUID for this transaction', unique=True, max_length=32, editable=False, blank=True)),
                ('notes', models.TextField(verbose_name='Any notes to go along with this Transaction.', blank=True)),
                ('_creation_timestamp', models.DateTimeField(auto_now_add=True, verbose_name='UTC time this transaction was recorded locally', db_index=True)),
                ('_posted_timestamp', models.DateTimeField(verbose_name='UTC time the transaction was posted', db_index=True)),
                ('finalized', models.BooleanField(default=False, verbose_name='Finalized transactions cannot be modified.')),
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('ledgers', models.ManyToManyField(to='ledger.Ledger', through='ledger.LedgerEntry')),
                ('voids', models.OneToOneField(related_name='voided_by', null=True, blank=True, to='ledger.Transaction')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TransactionRelatedObject',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('primary', models.BooleanField(default=False, verbose_name='Is this the primary related object?')),
                ('related_object_id', models.PositiveIntegerField(db_index=True)),
                ('related_object_content_type', models.ForeignKey(to='contenttypes.ContentType')),
                ('transaction', models.ForeignKey(related_name='related_objects', to='ledger.Transaction')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='transactionrelatedobject',
            unique_together=set([('transaction', 'related_object_content_type', 'related_object_id')]),
        ),
        migrations.AddField(
            model_name='ledgerentry',
            name='transaction',
            field=models.ForeignKey(related_name='entries', to='ledger.Transaction'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ledger',
            name='transactions',
            field=models.ManyToManyField(to='ledger.Transaction', through='ledger.LedgerEntry'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='ledger',
            unique_together=set([('type', 'entity_content_type', 'entity_id')]),
        ),
        migrations.AddField(
            model_name='invoicegenerationrecord',
            name='ledger',
            field=models.ForeignKey(to='ledger.Ledger'),
            preserve_default=True,
        ),
    ]
