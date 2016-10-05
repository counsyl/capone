# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.actions import void_transaction
from ledger.exceptions import TransactionBalanceException
from ledger.models import LedgerBalance
from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.tests.factories import CreditCardTransactionFactory
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import TransactionFactory
from ledger.tests.factories import TransactionTypeFactory
from ledger.tests.factories import UserFactory


class TransactionBase(TestCase):
    def setUp(self):
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.posted_timestamp = datetime.now()


class TestUnicodeMethods(TestCase):
    def test_unicode_methods(self):
        txn = TransactionFactory()

        tro = txn.related_objects.last()
        self.assertEqual(
            str(tro),
            'TransactionRelatedObject: CreditCardTransaction(id=%s)' % tro.related_object_id,  # nopep8
        )

        entry = txn.entries.last()
        self.assertEqual(
            str(entry),
            "LedgerEntry: $%s in %s" % (
                entry.amount,
                entry.ledger.name,
            )
        )

        ledger = LedgerFactory(name='foo')
        self.assertEqual(str(ledger), "Ledger foo")
        ledger = LedgerFactory(name='föo')
        self.assertEqual(str(ledger), "Ledger föo")

        ttype = TransactionTypeFactory(name='foo')
        self.assertEqual(str(ttype), "Transaction Type foo")

        balance = LedgerBalance.objects.last()
        self.assertEqual(
            str(balance),
            "LedgerBalance: %s for %s in %s" % (
                balance.balance,
                balance.related_object,
                balance.ledger,
            )
        )


class TestTransactionSummary(TransactionBase):
    def test_transaction_summary(self):
        ledger = LedgerFactory()
        amount = Decimal('500')
        ccx = CreditCardTransactionFactory()
        le1 = LedgerEntry(ledger=ledger, amount=credit(amount))
        le2 = LedgerEntry(ledger=ledger, amount=debit(amount))
        txn = TransactionFactory(
            evidence=[ccx],
            ledger_entries=[le1, le2]
        )

        self.assertEqual(
            txn.summary(),
            {
                'entries': [str(entry) for entry in txn.entries.all()],
                'related_objects': [
                    'TransactionRelatedObject: CreditCardTransaction(id=%s)' %
                    ccx.id,
                ],
            },
        )


class TestSettingExplicitTimestampField(TransactionBase):
    def test_repr(self):
        transaction = TransactionFactory()
        old_posted_timestamp = transaction.posted_timestamp
        transaction.posted_timestamp = datetime.now()
        transaction.save()
        self.assertNotEqual(
            old_posted_timestamp,
            transaction.posted_timestamp,
        )


class TestEditingTransactions(TestCase):
    """
    Test that validation is still done when editing a Transaction.

    Limited editing is allowed on a Transaction, e.g. for changing notes.
    However, we want to make sure that our balance invariants are still kept
    when editing a Transaction.
    """
    def test_editing_transactions(self):
        transaction = TransactionFactory()

        transaction.notes = 'foo'
        transaction.save()

        entry = transaction.entries.last()
        entry.amount += Decimal('1')
        entry.save()

        with self.assertRaises(TransactionBalanceException):
            transaction.save()


class TestDelete(TransactionBase):
    def test_cant_delete(self):
        transaction = TransactionFactory()
        self.assertRaises(PermissionDenied, transaction.delete)


class TestNonVoidFilter(TestCase):

    def setUp(self):
        self.order = OrderFactory()
        self.ar_ledger = LedgerFactory(name='A/R')
        self.cash_ledger = LedgerFactory(name='Cash')
        self.user = UserFactory()

    def add_transaction(self):
        return create_transaction(
            self.user,
            evidence=[self.order],
            ledger_entries=[
                LedgerEntry(
                    ledger=self.ar_ledger,
                    amount=credit(Decimal(50))),
                LedgerEntry(
                    ledger=self.cash_ledger,
                    amount=debit(Decimal(50))),
            ],
        )

    def filtered_out_by_non_void(self, transaction):
        queryset = Transaction.objects.filter(id=transaction.id)
        self.assertTrue(queryset.exists())
        return not queryset.non_void().exists()

    def test_non_void(self):
        transaction_1 = self.add_transaction()
        self.assertFalse(self.filtered_out_by_non_void(transaction_1))

        transaction_2 = self.add_transaction()
        self.assertFalse(self.filtered_out_by_non_void(transaction_2))

        voiding_transaction = void_transaction(transaction_2, self.user)
        self.assertFalse(self.filtered_out_by_non_void(transaction_1))
        self.assertTrue(self.filtered_out_by_non_void(transaction_2))
        self.assertTrue(self.filtered_out_by_non_void(voiding_transaction))
