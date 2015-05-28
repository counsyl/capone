# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    depends_on = (
        
    )

    def forwards(self, orm):

        # Changing field 'TransactionRelatedObject.transaction'
        db.alter_column(u'ledger_transactionrelatedobject', 'transaction_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ledger.Transaction']))
        # Adding index on 'TransactionRelatedObject', fields ['transaction']
        db.create_index(u'ledger_transactionrelatedobject', ['transaction_id'])


        # Changing field 'TransactionRelatedObject.related_object_content_type'
        db.alter_column(u'ledger_transactionrelatedobject', 'related_object_content_type_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType']))
        # Adding index on 'TransactionRelatedObject', fields ['related_object_content_type']
        db.create_index(u'ledger_transactionrelatedobject', ['related_object_content_type_id'])


        # Changing field 'Ledger.entity_content_type'
        db.alter_column(u'ledger_ledger', 'entity_content_type_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType']))
        # Adding index on 'Ledger', fields ['entity_content_type']
        db.create_index(u'ledger_ledger', ['entity_content_type_id'])


        # Changing field 'LedgerEntry.transaction'
        db.alter_column(u'ledger_ledgerentry', 'transaction_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ledger.Transaction']))
        # Adding index on 'LedgerEntry', fields ['transaction']
        db.create_index(u'ledger_ledgerentry', ['transaction_id'])


        # Changing field 'LedgerEntry.ledger'
        db.alter_column(u'ledger_ledgerentry', 'ledger_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ledger.Ledger']))
        # Adding index on 'LedgerEntry', fields ['ledger']
        db.create_index(u'ledger_ledgerentry', ['ledger_id'])


        # Changing field 'Transaction.created_by'
        db.alter_column(u'ledger_transaction', 'created_by_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User']))
        # Adding index on 'Transaction', fields ['created_by']
        db.create_index(u'ledger_transaction', ['created_by_id'])


        # Changing field 'Transaction.voids'
        db.alter_column(u'ledger_transaction', 'voids_id', self.gf('django.db.models.fields.related.OneToOneField')(unique=True, null=True, to=orm['ledger.Transaction']))
        # Adding index on 'Transaction', fields ['voids']
        db.create_index(u'ledger_transaction', ['voids_id'])

        # Adding unique constraint on 'Transaction', fields ['voids']
        db.create_unique(u'ledger_transaction', ['voids_id'])


        # Changing field 'InvoiceGenerationRecord.ledger'
        db.alter_column(u'ledger_invoicegenerationrecord', 'ledger_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ledger.Ledger']))
        # Adding index on 'InvoiceGenerationRecord', fields ['ledger']
        db.create_index(u'ledger_invoicegenerationrecord', ['ledger_id'])


    def backwards(self, orm):
        # Removing index on 'InvoiceGenerationRecord', fields ['ledger']
        db.delete_index(u'ledger_invoicegenerationrecord', ['ledger_id'])

        # Removing unique constraint on 'Transaction', fields ['voids']
        db.delete_unique(u'ledger_transaction', ['voids_id'])

        # Removing index on 'Transaction', fields ['voids']
        db.delete_index(u'ledger_transaction', ['voids_id'])

        # Removing index on 'Transaction', fields ['created_by']
        db.delete_index(u'ledger_transaction', ['created_by_id'])

        # Removing index on 'LedgerEntry', fields ['ledger']
        db.delete_index(u'ledger_ledgerentry', ['ledger_id'])

        # Removing index on 'LedgerEntry', fields ['transaction']
        db.delete_index(u'ledger_ledgerentry', ['transaction_id'])

        # Removing index on 'Ledger', fields ['entity_content_type']
        db.delete_index(u'ledger_ledger', ['entity_content_type_id'])

        # Removing index on 'TransactionRelatedObject', fields ['related_object_content_type']
        db.delete_index(u'ledger_transactionrelatedobject', ['related_object_content_type_id'])

        # Removing index on 'TransactionRelatedObject', fields ['transaction']
        db.delete_index(u'ledger_transactionrelatedobject', ['transaction_id'])


        # Changing field 'TransactionRelatedObject.transaction'
        db.alter_column(u'ledger_transactionrelatedobject', 'transaction_id', self.gf('django.db.models.fields.IntegerField')(db_column='transaction_id'))

        # Changing field 'TransactionRelatedObject.related_object_content_type'
        db.alter_column(u'ledger_transactionrelatedobject', 'related_object_content_type_id', self.gf('django.db.models.fields.IntegerField')(db_column='related_object_content_type_id'))

        # Changing field 'Ledger.entity_content_type'
        db.alter_column(u'ledger_ledger', 'entity_content_type_id', self.gf('django.db.models.fields.IntegerField')(db_column='entity_content_type_id'))

        # Changing field 'LedgerEntry.transaction'
        db.alter_column(u'ledger_ledgerentry', 'transaction_id', self.gf('django.db.models.fields.IntegerField')(db_column='transaction_id'))

        # Changing field 'LedgerEntry.ledger'
        db.alter_column(u'ledger_ledgerentry', 'ledger_id', self.gf('django.db.models.fields.IntegerField')(db_column='ledger_id'))

        # Changing field 'Transaction.created_by'
        db.alter_column(u'ledger_transaction', 'created_by_id', self.gf('django.db.models.fields.IntegerField')(db_column='created_by_id'))

        # Changing field 'Transaction.voids'
        db.alter_column(u'ledger_transaction', 'voids_id', self.gf('django.db.models.fields.IntegerField')(db_column='voids_id'))

        # Changing field 'InvoiceGenerationRecord.ledger'
        db.alter_column(u'ledger_invoicegenerationrecord', 'ledger_id', self.gf('django.db.models.fields.IntegerField')(db_column='ledger_id'))

    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '75'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'ledger.invoicegenerationrecord': {
            'Meta': {'object_name': 'InvoiceGenerationRecord'},
            '_creation_timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            '_invoice_timestamp': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '24', 'decimal_places': '4'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ledger': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ledger.Ledger']"})
        },
        u'ledger.ledger': {
            'Meta': {'unique_together': "(('type', 'entity_content_type', 'entity_id'),)", 'object_name': 'Ledger'},
            'entity_content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            'entity_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'transactions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['ledger.Transaction']", 'through': u"orm['ledger.LedgerEntry']", 'symmetrical': 'False'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        u'ledger.ledgerentry': {
            'Meta': {'object_name': 'LedgerEntry'},
            'action_type': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '24', 'decimal_places': '4'}),
            'entry_id': ('uuidfield.fields.UUIDField', [], {'unique': 'True', 'max_length': '32', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ledger': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'entries'", 'to': u"orm['ledger.Ledger']"}),
            'transaction': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'entries'", 'to': u"orm['ledger.Transaction']"})
        },
        u'ledger.transaction': {
            'Meta': {'object_name': 'Transaction'},
            '_creation_timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            '_posted_timestamp': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            'finalized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ledgers': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['ledger.Ledger']", 'through': u"orm['ledger.LedgerEntry']", 'symmetrical': 'False'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'transaction_id': ('uuidfield.fields.UUIDField', [], {'unique': 'True', 'max_length': '32', 'blank': 'True'}),
            'voids': ('django.db.models.fields.related.OneToOneField', [], {'blank': 'True', 'related_name': "'voided_by'", 'unique': 'True', 'null': 'True', 'to': u"orm['ledger.Transaction']"})
        },
        u'ledger.transactionrelatedobject': {
            'Meta': {'unique_together': "(('transaction', 'related_object_content_type', 'related_object_id'),)", 'object_name': 'TransactionRelatedObject'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'primary': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'related_object_content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            'related_object_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'transaction': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'related_objects'", 'to': u"orm['ledger.Transaction']"})
        }
    }

    complete_apps = ['ledger']