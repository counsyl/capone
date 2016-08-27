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
from ledger.tests.factories import CreditCardTransactionFactory
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import TransactionFactory
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


class TestUnicodeMethods(TransactionBase):
    def test_unicode_methods(self):
        txn = TransactionFactory()

        tro = txn.related_objects.last()
        self.assertEqual(
            unicode(tro),
            u'TransactionRelatedObject: CreditCardTransaction(id=%s)' % tro.related_object_id,  # nopep8
        )

        entry = txn.entries.last()
        self.assertEqual(
            repr(entry),
            "<LedgerEntry: LedgerEntry: $%s in %s>" % (
                entry.amount,
                entry.ledger.name,
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
                'entries': [unicode(entry) for entry in txn.entries.all()],
                'related_objects': [
                    u'TransactionRelatedObject: CreditCardTransaction(id=%s)' %
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


class TestUnBalance(TransactionBase):
    def test_only_credits(self):
        # User 1 trying to pay User 2, but only debits from own ledger
        with self.assertRaises(Transaction.TransactionBalanceException):
            create_transaction(
                self.user1,
                evidence=[self.user2],
                ledger_entries=[
                    LedgerEntry(
                        ledger=self.user1_ledger,
                        amount=Decimal('-500'))
                ],
            )

    def test_only_debits(self):
        # User 1 trying to pay User 2, but only credits User 2's ledger
        with self.assertRaises(Transaction.TransactionBalanceException):
            create_transaction(
                self.user1,
                evidence=[self.user2],
                ledger_entries=[
                    LedgerEntry(
                        ledger=self.user2_ledger,
                        amount=Decimal('500'))
                ],
            )

    def test_mismatch(self):
        # User 1 pays User 2, but credits too much
        with self.assertRaises(Transaction.TransactionBalanceException):
            create_transaction(
                self.user1,
                evidence=[self.user2],
                ledger_entries=[
                    LedgerEntry(
                        ledger=self.user1_ledger,
                        amount=Decimal('-499')),
                    LedgerEntry(
                        ledger=self.user2_ledger,
                        amount=Decimal('500'))
                ],
            )

    def test_rounding_mismatch(self):
        # User 1 pays 499.99995 to User 2, but their client rounded wrong
        with self.assertRaises(Transaction.TransactionBalanceException):
            create_transaction(
                self.user1,
                evidence=[self.user2],
                ledger_entries=[
                    LedgerEntry(
                        ledger=self.user1_ledger,
                        amount=Decimal('-499.99995')),  # We round this to -500
                    # Assume their client rounds -499.99995 to -499.9999 and
                    # then abs() it
                    LedgerEntry(
                        ledger=self.user2_ledger,
                        amount=Decimal('499.9999'))
                ],
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

        with self.assertRaises(Transaction.TransactionBalanceException):
            transaction.save()


class TestRounding(TransactionBase):
    def _create_transaction_and_compare_to_amount(
            self, amount, comparison_amount=None):
        transaction = create_transaction(
            self.user2,
            ledger_entries=[
                LedgerEntry(
                    ledger=self.user1_ledger,
                    amount=amount),
                LedgerEntry(
                    ledger=self.user2_ledger,
                    amount=-amount),
            ]
        )

        entry = transaction.entries.get(ledger=self.user1_ledger)
        if comparison_amount:
            self.assertNotEqual(entry.amount, amount)
            self.assertEqual(entry.amount, comparison_amount)
        else:
            self.assertEqual(entry.amount, amount)

    def test_precision(self):
        self._create_transaction_and_compare_to_amount(
            Decimal('-499.9999'))

    def test_round_up(self):
        self._create_transaction_and_compare_to_amount(
            Decimal('499.99995'), Decimal('500'))

    def test_round_down(self):
        self._create_transaction_and_compare_to_amount(
            Decimal('499.99994'), Decimal('499.9999'))

    def test_round_up_negative(self):
        self._create_transaction_and_compare_to_amount(
            Decimal('-499.99994'), Decimal('-499.9999'))

    def test_round_down_negative(self):
        self._create_transaction_and_compare_to_amount(
            Decimal('-499.99995'), Decimal('-500'))


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
