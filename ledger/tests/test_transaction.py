from datetime import datetime
from decimal import Decimal as D

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.tests.factories import UserFactory
from ledger.timezone import to_utc


class TransactionBase(TestCase):
    def setUp(self):
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user1_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.user1,
            Ledger.LEDGER_ACCOUNTS_RECEIVABLE)
        self.user2_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.user2,
            Ledger.LEDGER_ACCOUNTS_RECEIVABLE)
        self.posted_timestamp = to_utc(datetime.utcnow())

    def new_transaction(self, related_object, created_by):
        return Transaction.objects.create_for_related_object(
            related_object, created_by=created_by,
            _posted_timestamp=self.posted_timestamp)


class TestUnBalance(TransactionBase):
    def test_only_credits(self):
        # User 1 trying to pay User 2, but only debits from own ledger
        transaction = self.new_transaction(self.user2, self.user1)
        LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=D('-500'))
        self.assertRaises(
            Transaction.TransactionBalanceException, transaction.validate)

    def test_only_debits(self):
        # User 1 trying to pay User 2, but only credits User 2's ledger
        transaction = self.new_transaction(self.user2, self.user1)
        LedgerEntry.objects.create(
            ledger=self.user2_ledger,
            transaction=transaction,
            amount=D('500'))
        self.assertRaises(
            Transaction.TransactionBalanceException, transaction.validate)

    def test_mismatch(self):
        # User 1 pays User 2, but credits too much
        transaction = self.new_transaction(self.user2, self.user1)
        LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=D('-499'))
        LedgerEntry.objects.create(
            ledger=self.user2_ledger,
            transaction=transaction,
            amount=D('500'))
        self.assertRaises(
            Transaction.TransactionBalanceException, transaction.validate)

    def test_rounding_mismatch(self):
        # User 1 pays 499.99995 to User 2, but their client rounded wrong
        transaction = self.new_transaction(self.user2, self.user1)
        LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=D('-499.99995'))  # We round this to -500
        # Assume their client rounds -499.99995 to -499.9999 and then abs() it
        LedgerEntry.objects.create(
            ledger=self.user2_ledger,
            transaction=transaction,
            amount=D('499.9999'))
        self.assertRaises(
            Transaction.TransactionBalanceException, transaction.validate)


class TestRounding(TransactionBase):
    def test_precision(self):
        amount = D('-499.9999')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertEqual(entry.amount, amount)

    def test_round_up(self):
        amount = D('499.99995')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertNotEqual(entry.amount, amount)
        self.assertEqual(entry.amount, D('500'))

    def test_round_down(self):
        amount = D('499.99994')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertNotEqual(entry.amount, amount)
        self.assertEqual(entry.amount, D('499.9999'))

    def test_round_up_negative(self):
        amount = D('-499.99994')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertNotEqual(entry.amount, amount)
        self.assertEqual(entry.amount, D('-499.9999'))

    def test_round_down_negative(self):
        amount = D('-499.99995')
        transaction = self.new_transaction(self.user2, self.user2)
        entry = LedgerEntry.objects.create(
            ledger=self.user1_ledger,
            transaction=transaction,
            amount=amount)
        entry = LedgerEntry.objects.get(id=entry.id)
        self.assertNotEqual(entry.amount, amount)
        self.assertEqual(entry.amount, D('-500'))


class TestDelete(TransactionBase):
    def test_cant_delete(self):
        transaction = self.new_transaction(self.user2, self.user2)
        self.assertRaises(PermissionDenied, transaction.delete)
