# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):



    def forwards(self, orm):
        # Adding model 'InvoiceGenerationRecord'
        db.create_table(u'ledger_invoicegenerationrecord', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('_creation_timestamp', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('_invoice_timestamp', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('ledger', self.gf('django.db.models.fields.IntegerField')(default=0, db_column='ledger_id')),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=24, decimal_places=4)),
        ))
        db.send_create_signal(u'ledger', ['InvoiceGenerationRecord'])

        # Adding model 'TransactionRelatedObject'
        db.create_table(u'ledger_transactionrelatedobject', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('transaction', self.gf('django.db.models.fields.IntegerField')(default=0, db_column='transaction_id')),
            ('primary', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('related_object_content_type', self.gf('django.db.models.fields.IntegerField')(default=0, db_column='related_object_content_type_id')),
            ('related_object_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
        ))
        db.send_create_signal(u'ledger', ['TransactionRelatedObject'])

        # Adding unique constraint on 'TransactionRelatedObject', fields ['transaction', 'related_object_content_type', 'related_object_id']
        db.create_unique(u'ledger_transactionrelatedobject', ['transaction_id', 'related_object_content_type_id', 'related_object_id'])

        # Adding model 'Transaction'
        db.create_table(u'ledger_transaction', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('transaction_id', self.gf('uuidfield.fields.UUIDField')(unique=True, max_length=32, blank=True)),
            ('voids', self.gf('django.db.models.fields.IntegerField')(default=0, db_column='voids_id')),
            ('notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('created_by', self.gf('django.db.models.fields.IntegerField')(default=0, db_column='created_by_id')),
            ('_creation_timestamp', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('_posted_timestamp', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('finalized', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'ledger', ['Transaction'])

        # Adding model 'Ledger'
        db.create_table(u'ledger_ledger', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('entity_content_type', self.gf('django.db.models.fields.IntegerField')(default=0, db_column='entity_content_type_id')),
            ('entity_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'ledger', ['Ledger'])

        # Adding unique constraint on 'Ledger', fields ['type', 'entity_content_type', 'entity_id']
        db.create_unique(u'ledger_ledger', ['type', 'entity_content_type_id', 'entity_id'])

        # Adding model 'LedgerEntry'
        db.create_table(u'ledger_ledgerentry', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ledger', self.gf('django.db.models.fields.IntegerField')(default=0, db_column='ledger_id')),
            ('transaction', self.gf('django.db.models.fields.IntegerField')(default=0, db_column='transaction_id')),
            ('entry_id', self.gf('uuidfield.fields.UUIDField')(unique=True, max_length=32, blank=True)),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=24, decimal_places=4)),
            ('action_type', self.gf('django.db.models.fields.CharField')(max_length=128, blank=True)),
        ))
        db.send_create_signal(u'ledger', ['LedgerEntry'])


    def backwards(self, orm):
        # Removing unique constraint on 'Ledger', fields ['type', 'entity_content_type', 'entity_id']
        db.delete_unique(u'ledger_ledger', ['type', 'entity_content_type_id', 'entity_id'])

        # Removing unique constraint on 'TransactionRelatedObject', fields ['transaction', 'related_object_content_type', 'related_object_id']
        db.delete_unique(u'ledger_transactionrelatedobject', ['transaction_id', 'related_object_content_type_id', 'related_object_id'])

        # Deleting model 'InvoiceGenerationRecord'
        db.delete_table(u'ledger_invoicegenerationrecord')

        # Deleting model 'TransactionRelatedObject'
        db.delete_table(u'ledger_transactionrelatedobject')

        # Deleting model 'Transaction'
        db.delete_table(u'ledger_transaction')

        # Deleting model 'Ledger'
        db.delete_table(u'ledger_ledger')

        # Deleting model 'LedgerEntry'
        db.delete_table(u'ledger_ledgerentry')


    models = {
        u'ledger.invoicegenerationrecord': {
            'Meta': {'object_name': 'InvoiceGenerationRecord'},
            '_creation_timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            '_invoice_timestamp': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '24', 'decimal_places': '4'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ledger': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_column': "'ledger_id'"})
        },
        u'ledger.ledger': {
            'Meta': {'unique_together': "(('type', 'entity_content_type', 'entity_id'),)", 'object_name': 'Ledger'},
            'entity_content_type': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_column': "'entity_content_type_id'"}),
            'entity_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        u'ledger.ledgerentry': {
            'Meta': {'object_name': 'LedgerEntry'},
            'action_type': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '24', 'decimal_places': '4'}),
            'entry_id': ('uuidfield.fields.UUIDField', [], {'unique': 'True', 'max_length': '32', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ledger': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_column': "'ledger_id'"}),
            'transaction': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_column': "'transaction_id'"})
        },
        u'ledger.transaction': {
            'Meta': {'object_name': 'Transaction'},
            '_creation_timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            '_posted_timestamp': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'created_by': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_column': "'created_by_id'"}),
            'finalized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'transaction_id': ('uuidfield.fields.UUIDField', [], {'unique': 'True', 'max_length': '32', 'blank': 'True'}),
            'voids': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_column': "'voids_id'"})
        },
        u'ledger.transactionrelatedobject': {
            'Meta': {'unique_together': "(('transaction', 'related_object_content_type', 'related_object_id'),)", 'object_name': 'TransactionRelatedObject'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'primary': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'related_object_content_type': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_column': "'related_object_content_type_id'"}),
            'related_object_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'transaction': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_column': "'transaction_id'"})
        }
    }

    complete_apps = ['ledger']