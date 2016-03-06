import mock
from datetime import datetime
from decimal import Decimal as D

from django.contrib.auth.models import User
from django.test import TestCase

from ledger.api.actions import Charge
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.actions import LedgerEntryAction
from ledger.api.actions import Payment
from ledger.api.actions import Refund
from ledger.api.actions import TransactionContext
from ledger.api.actions import TransferAmount
from ledger.api.actions import void_transaction
from ledger.api.actions import WriteDown
from ledger.models import Ledger
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LEDGER_CASH
from ledger.models import LedgerEntry
from ledger.models import LEDGER_REVENUE
from ledger.models import Transaction
from ledger.tests.factories import UserFactory


class LedgerEntryActionSetUp(TestCase):
    def setUp(self):
        super(LedgerEntryActionSetUp, self).setUp()
        self.entity_1 = UserFactory()
        self.entity_2 = UserFactory()
        self.creation_user = UserFactory()
        self.entity_1_ar_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_1, LEDGER_ACCOUNTS_RECEIVABLE)
        self.entity_1_rev_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_1, LEDGER_REVENUE)
        self.entity_1_cash_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_1, LEDGER_CASH)
        self.entity_2_ar_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_2, LEDGER_ACCOUNTS_RECEIVABLE)
        self.entity_2_rev_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_2, LEDGER_REVENUE)
        self.entity_2_cash_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_2, LEDGER_CASH)


class _TestLedgerActionBase(TestCase):
    """Child classes must define ACTION_CLASS."""
    ACTION_CLASS = None

    def setUp(self):
        super(_TestLedgerActionBase, self).setUp()
        self.entity = UserFactory()
        self.creation_user = UserFactory()
        self.transaction = TransactionContext(
            self.creation_user, self.creation_user)

    def test_number_entries(self):
        """Test that recording an amount generates two LedgerEntries."""
        self.assertEqual(Ledger.objects.count(), 0)
        self.assertEqual(LedgerEntry.objects.count(), 0)
        with self.transaction as txn:
            txn.record_action(self.ACTION_CLASS(self.entity, D(100)))
        self.assertEqual(Ledger.objects.count(), 2)
        self.assertEqual(LedgerEntry.objects.count(), 2)

    def test_amount_validation(self):
        """Ensure that credits are negative, debits are positive."""
        self.assertTrue(self.ACTION_CLASS.validate_amount(D(100)))
        self.assertTrue(self.ACTION_CLASS.validate_amount(D(0)))
        self.assertRaises(ValueError, self.ACTION_CLASS.validate_amount, D(-1))

        # Test that the ValueError above is properly propagated
        self.assertRaises(ValueError, self.ACTION_CLASS, self.entity, D(-1))

    def test_multiple_entries_in_transaction(self):
        """Multiple LedgerEntries can be put into a single transaction."""
        with TransactionContext(
                self.creation_user, self.creation_user) as txn_1:
            txn_1.record_action(self.ACTION_CLASS(self.entity, D(100)))
        with TransactionContext(
                self.creation_user, self.creation_user) as txn_2:
            txn_2.record_action(self.ACTION_CLASS(self.entity, D(100)))
            txn_2.record_action(self.ACTION_CLASS(self.entity, D(10)))
        self.assertNotEqual(txn_1, txn_2)
        self.assertEqual(txn_2.transaction.entries.count(), 4)

    def test_timestamp(self):
        timestamp = datetime.now()
        with TransactionContext(
                self.creation_user,
                self.creation_user,
                posted_timestamp=timestamp) as txn:
            txn.record_action(self.ACTION_CLASS(self.entity, D(100)))
        self.assertEqual(txn.transaction.posted_timestamp, timestamp)
        txn = Transaction.objects.get(id=txn.transaction.id)
        self.assertEqual(txn.posted_timestamp, timestamp)


class TestCharge(_TestLedgerActionBase):
    ACTION_CLASS = Charge


class TestPayment(_TestLedgerActionBase):
    ACTION_CLASS = Payment


class TestWriteDown(_TestLedgerActionBase):
    ACTION_CLASS = WriteDown


class TestRefund(_TestLedgerActionBase):
    ACTION_CLASS = Refund


class TestReprs(TestCase):
    def test_reprs(self):
        User.objects.all().delete()

        CLASSES_TO_REPRS = {
            Charge: '<Charge: 100 <User: %s>>',
            Payment: '<Payment: 100 <User: %s>>',
            WriteDown: '<WriteDown: 100 <User: %s>>',
            Refund: '<Refund: 100 <User: %s>>',
        }

        entity = UserFactory()

        for _class, _repr in CLASSES_TO_REPRS.items():
            self.assertEqual(
                repr(_class(entity, D(100))),
                _repr % entity.username)

        entity2 = UserFactory()

        self.assertEqual(
            repr(TransferAmount(entity, entity2, D(100))),
            "<TransferAmount: 100 from <User: %s> to <User: %s>>"  # nopep8
            % (entity.username, entity2.username),
        )


class TestLedgerEntryAction(LedgerEntryActionSetUp):
    """
    Test Errors from LedgerEntryAction._get_debit_ledger and _get_credit_ledger
    """
    def test_not_implemented_errors(self):
        amount = D(100)

        with self.assertRaises(NotImplementedError):
            with TransactionContext(
                    self.creation_user, self.creation_user) as txn:
                txn.record_action(LedgerEntryAction(amount))

        ledger = Ledger.objects.last()

        with mock.patch.object(
                LedgerEntryAction, '_get_credit_ledger', return_value=ledger):
            with self.assertRaises(NotImplementedError):
                with TransactionContext(
                        self.creation_user, self.creation_user) as txn:
                    txn.record_action(LedgerEntryAction(amount))

        with mock.patch.object(
                LedgerEntryAction, '_get_credit_ledger', return_value=ledger):
            with mock.patch.object(
                    LedgerEntryAction,
                    '_get_debit_ledger',
                    return_value=ledger):
                with TransactionContext(
                        self.creation_user, self.creation_user) as txn:
                    txn.record_action(LedgerEntryAction(amount))


class TestTransferAction(LedgerEntryActionSetUp):
    def test_simple_transfer(self):
        amount = D(100)

        self.assertEqual(Transaction.objects.count(), 0)

        # First charge entity_1
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record_action(Charge(self.entity_1, amount))
        self.assertEqual(Transaction.objects.count(), 1)

        self.assertEqual(self.entity_1_ar_ledger.get_balance(), amount)
        self.assertEqual(self.entity_1_rev_ledger.get_balance(), -amount)

        # And transfer the entire balance to entity_2
        with TransactionContext(self.creation_user, self.creation_user)\
                as transfer_txn:
            transfer_txn.record_action(
                TransferAmount(self.entity_1, self.entity_2, amount))
        # This should have only created a single new transaction
        self.assertEqual(Transaction.objects.count(), 2)
        # ...with four ledger entries
        self.assertEqual(transfer_txn.transaction.entries.count(), 4)

        self.assertEqual(self.entity_1_ar_ledger.get_balance(), 0)
        self.assertEqual(self.entity_1_rev_ledger.get_balance(), 0)
        self.assertEqual(self.entity_2_ar_ledger.get_balance(), amount)
        self.assertEqual(self.entity_2_rev_ledger.get_balance(), -amount)

    def test_void_transfer(self):
        amount = D(100)
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record_action(Charge(self.entity_1, amount))
        with TransactionContext(self.creation_user, self.creation_user)\
                as transfer_txn:
            transfer_txn.record_action(
                TransferAmount(self.entity_1, self.entity_2, amount))

        # Void the charge
        void_txn = void_transaction(
            transfer_txn.transaction, self.creation_user)

        self.assertEqual(void_txn.voids, transfer_txn.transaction)

        self.assertEqual(self.entity_1_ar_ledger.get_balance(), amount)
        self.assertEqual(self.entity_1_rev_ledger.get_balance(), -amount)

        self.assertEqual(self.entity_2_ar_ledger.get_balance(), 0)
        self.assertEqual(self.entity_2_rev_ledger.get_balance(), 0)


class TestRefundBalance(LedgerEntryActionSetUp):
    def setUp(self):
        super(TestRefundBalance, self).setUp()
        self.charge_amount = D(1000)
        self.payment_amount = D(1500)

        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record_action(Charge(self.entity_1, self.charge_amount))

        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record_action(Payment(self.entity_1, self.payment_amount))

    def test_refund(self):
        refund_amount = self.payment_amount - self.charge_amount
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record_action(Refund(self.entity_1, refund_amount))

        self.assertEqual(self.entity_1_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_1_cash_ledger.get_balance(),
                         self.payment_amount - refund_amount)
        self.assertEqual(self.entity_1_cash_ledger.get_balance(),
                         self.charge_amount)
        self.assertEqual(self.entity_1_rev_ledger.get_balance(),
                         -1 * self.charge_amount)

    def test_refund_too_big(self):
        self.assertEqual(self.entity_1_rev_ledger.get_balance(),
                         -1 * self.charge_amount)
        # Refund the entire payment and ensure they still owe money
        refund_amount = self.payment_amount
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record_action(Refund(self.entity_1, refund_amount))

        self.assertEqual(self.entity_1_ar_ledger.get_balance(),
                         self.charge_amount)
        self.assertEqual(self.entity_1_cash_ledger.get_balance(), D(0))
        # Revenue should be unchanged because it doesn't depend on actually
        # receiving payments
        self.assertEqual(self.entity_1_rev_ledger.get_balance(),
                         -1 * self.charge_amount)


class TestCreditAndDebit(TestCase):
    """
    Test that `credit` and `debit` return the correctly signed amounts.
    """
    AMOUNT = D(100)

    def assertPositive(self, amount):
        self.assertGreaterEqual(amount, 0)

    def assertNegative(self, amount):
        self.assertLess(amount, 0)

    def test_credit_and_debit_helper_functions(self):
        with mock.patch('ledger.api.actions.settings') as mock_settings:
            mock_settings.DEBITS_ARE_NEGATIVE = True
            self.assertPositive(credit(self.AMOUNT))
            self.assertNegative(debit(self.AMOUNT))
        with mock.patch('ledger.api.actions.settings') as mock_settings:
            mock_settings.DEBITS_ARE_NEGATIVE = False
            self.assertNegative(credit(self.AMOUNT))
            self.assertPositive(debit(self.AMOUNT))

    def test_validation_error(self):
        self.assertRaises(ValueError, credit, -self.AMOUNT)
        self.assertRaises(ValueError, debit, -self.AMOUNT)
