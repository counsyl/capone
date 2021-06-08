# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-12-20 17:00

import uuid
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import capone.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ledger',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text='Name of this ledger', max_length=255, unique=True)),
                ('number',
                 models.PositiveIntegerField(help_text='Unique numeric identifier for this ledger', unique=True)),
                ('description', models.TextField(blank=True, help_text='Any notes to go along with this Transaction.')),
                ('increased_by_debits', models.BooleanField(default=None,
                                                            help_text='All accounts (and their corresponding ledgers) are of one of two types: either debits increase the value of an account or credits do.  By convention, asset and expense accounts are of the former type, while liabilities, equity, and revenue are of the latter.')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='LedgerBalance',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('related_object_id', models.PositiveIntegerField(db_index=True)),
                ('balance', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=24)),
                ('ledger', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='capone.Ledger')),
                ('related_object_content_type',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
            ],
        ),
        migrations.CreateModel(
            name='LedgerEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('entry_id', models.UUIDField(default=uuid.uuid4, help_text='UUID for this ledger entry')),
                ('amount', models.DecimalField(decimal_places=4,
                                               help_text='Amount for this entry.  Debits are positive, and credits are negative.',
                                               max_digits=24)),
                ('ledger', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries',
                                             to='capone.Ledger')),
            ],
            options={
                'verbose_name_plural': 'ledger entries',
            },
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('transaction_id', models.UUIDField(default=uuid.uuid4, help_text='UUID for this transaction')),
                ('notes', models.TextField(blank=True, help_text='Any notes to go along with this Transaction.')),
                ('posted_timestamp', models.DateTimeField(db_index=True,
                                                          help_text='Time the transaction was posted.  Change this field to model retroactive ledger entries.')),
                ('created_by',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('ledgers', models.ManyToManyField(through='capone.LedgerEntry', to='capone.Ledger')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TransactionRelatedObject',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('related_object_id', models.PositiveIntegerField(db_index=True)),
                ('related_object_content_type',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
                ('transaction',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_objects',
                                   to='capone.Transaction')),
            ],
        ),
        migrations.CreateModel(
            name='TransactionType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text='Name of this transaction type', max_length=255, unique=True)),
                ('description', models.TextField(blank=True, help_text='Any notes to go along with this Transaction.')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='transaction',
            name='type',
            field=models.ForeignKey(default=capone.models.get_or_create_manual_transaction_type_id,
                                    on_delete=django.db.models.deletion.CASCADE, to='capone.TransactionType'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='voids',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                       related_name='voided_by', to='capone.Transaction'),
        ),
        migrations.AddField(
            model_name='ledgerentry',
            name='transaction',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries',
                                    to='capone.Transaction'),
        ),
        migrations.AlterUniqueTogether(
            name='transactionrelatedobject',
            unique_together=set([('transaction', 'related_object_content_type', 'related_object_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='ledgerbalance',
            unique_together=set([('ledger', 'related_object_content_type', 'related_object_id')]),
        ),
    ]
