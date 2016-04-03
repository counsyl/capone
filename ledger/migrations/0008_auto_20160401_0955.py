# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from decimal import Decimal

from ledger.utils import REBUILD_LEDGER_BALANCES_SQL


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('ledger', '0007_auto_20160205_1907'),
    ]

    operations = [
        migrations.CreateModel(
            name='LedgerBalance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('related_object_id', models.PositiveIntegerField(db_index=True)),
                ('balance', models.DecimalField(default=Decimal('0'), max_digits=24, decimal_places=4)),
                ('ledger', models.ForeignKey(to='ledger.Ledger')),
                ('related_object_content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='ledgerbalance',
            unique_together=set([('ledger', 'related_object_content_type', 'related_object_id')]),
        ),
        migrations.RunSQL(REBUILD_LEDGER_BALANCES_SQL),
    ]
