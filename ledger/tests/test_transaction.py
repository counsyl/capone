from datetime import datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.actions import void_transaction
from ledger.models import Ledger
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import UserFactory


class TransactionBase(TestCase):
    def setUp(self):
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user1_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.user1,
            LEDGER_ACCOUNTS_RECEIVABLE)
        self.user2_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.user2,
            LEDGER_ACCOUNTS_RECEIVABLE)
        self.posted_timestamp = datetime.now()

    def new_transaction(self, related_object, created_by):
        return Transaction.objects.create_for_related_object(
            related_object, created_by=created_by,
            posted_timestamp=self.posted_timestamp)


class TestLedgerEntry(TransactionBase):
    def test_repr(self):
        transaction = self.new_transaction(self.user2, self.user1)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=Decimal('-500'))
        self.assertEqual(
            repr(entry),
            "<LedgerEntry: LedgerEntry (%s)  for $-500>" % entry.entry_id,
        )


class TestSettingExplicitTimestampField(TransactionBase):
    def test_repr(self):
        transaction = self.new_transaction(self.user2, self.user1)
        old_posted_timestamp = transaction.posted_timestamp
        transaction.posted_timestamp = datetime.now()
        transaction.save()
        self.assertNotEqual(
            old_posted_timestamp,
            transaction.posted_timestamp,
        )


class TestUnBalance(TransactionBase):
    def test_only_credits(self):
        # User 1 trying to pay User 2, but only debits from own ledger
        transaction = self.new_transaction(self.user2, self.user1)
        LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=Decimal('-500'))
        self.assertRaises(
            Transaction.TransactionBalanceException, transaction.validate)

    def test_only_debits(self):
        # User 1 trying to pay User 2, but only credits User 2's ledger
        transaction = self.new_transaction(self.user2, self.user1)
        LedgerEntry.objects.create(
            ledger=self.user2_ledger,
            transaction=transaction,
            amount=Decimal('500'))
        self.assertRaises(
            Transaction.TransactionBalanceException, transaction.validate)

    def test_mismatch(self):
        # User 1 pays User 2, but credits too much
        transaction = self.new_transaction(self.user2, self.user1)
        LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=Decimal('-499'))
        LedgerEntry.objects.create(
            ledger=self.user2_ledger,
            transaction=transaction,
            amount=Decimal('500'))
        self.assertRaises(
            Transaction.TransactionBalanceException, transaction.validate)

    def test_rounding_mismatch(self):
        # User 1 pays 499.99995 to User 2, but their client rounded wrong
        transaction = self.new_transaction(self.user2, self.user1)
        LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=Decimal('-499.99995'))  # We round this to -500
        # Assume their client rounds -499.99995 to -499.9999 and then abs() it
        LedgerEntry.objects.create(
            ledger=self.user2_ledger,
            transaction=transaction,
            amount=Decimal('499.9999'))
        self.assertRaises(
            Transaction.TransactionBalanceException, transaction.validate)


class TestRounding(TransactionBase):
    def test_precision(self):
        amount = Decimal('-499.9999')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertEqual(entry.amount, amount)

    def test_round_up(self):
        amount = Decimal('499.99995')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertNotEqual(entry.amount, amount)
        self.assertEqual(entry.amount, Decimal('500'))

    def test_round_down(self):
        amount = Decimal('499.99994')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertNotEqual(entry.amount, amount)
        self.assertEqual(entry.amount, Decimal('499.9999'))

    def test_round_up_negative(self):
        amount = Decimal('-499.99994')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertNotEqual(entry.amount, amount)
        self.assertEqual(entry.amount, Decimal('-499.9999'))

    def test_round_down_negative(self):
        amount = Decimal('-499.99995')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertNotEqual(entry.amount, amount)
        self.assertEqual(entry.amount, Decimal('-500'))


class TestDelete(TransactionBase):
    def test_cant_delete(self):
        transaction = self.new_transaction(self.user2, self.user2)
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
