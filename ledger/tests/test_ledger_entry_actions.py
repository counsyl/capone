import mock
from datetime import datetime
from decimal import Decimal as D

from django.test import TestCase
from django.utils.timezone import get_current_timezone
from pytz import UTC

from ledger.api.actions import Charge
from ledger.api.actions import LedgerEntryAction
from ledger.api.actions import Payment
from ledger.api.actions import Refund
from ledger.api.actions import TransactionContext
from ledger.api.actions import TransferAmount
from ledger.api.actions import VoidTransaction
from ledger.api.actions import WriteDown
from ledger.models import Ledger
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LEDGER_CASH
from ledger.models import LedgerEntry
from ledger.models import LEDGER_REVENUE
from ledger.models import Transaction
from ledger.timezone import to_utc
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


class TestPostedTimestampTimezonesMixin(object):
    def _populate_timezones(self):
        self.local_timezone = get_current_timezone()
        # A timestamp that happens shortly before a US/Pacific
        # daylight savings time fall-back event.
        self.fall_back_utc = datetime(2002, 10, 27, 8, 30, 0, tzinfo=UTC)
        self.fall_back_local = self._localize(self.fall_back_utc)

        # A timestamp whose naive version, when interpreted as if
        # it was in US/Pacific, happens shortly after a daylight
        # savings time fall-forward event.
        self.spring_forward_utc = datetime(2002, 4, 7, 2, 30, 0, tzinfo=UTC)
        self.spring_forward_local = self._localize(self.spring_forward_utc)

    def _localize(self, timestamp):
        if not hasattr(timestamp, 'tzinfo') or not timestamp.tzinfo:
            timestamp = self.local_timezone.localize(timestamp)
        return timestamp.astimezone(self.local_timezone)


class _TestLedgerActionBase(TestCase,
                            TestPostedTimestampTimezonesMixin):
    """Child classes must define ACTION_CLASS."""
    ACTION_CLASS = None

    def setUp(self):
        super(_TestLedgerActionBase, self).setUp()
        self.entity = UserFactory()
        self.creation_user = UserFactory()
        self.transaction = TransactionContext(
            self.creation_user, self.creation_user)
        self._populate_timezones()

    def test_number_entries(self):
        """Test that recording an amount generates two LedgerEntries."""
        self.assertEqual(Ledger.objects.count(), 0)
        self.assertEqual(LedgerEntry.objects.count(), 0)
        with self.transaction as txn:
            txn.record(self.ACTION_CLASS(self.entity, D(100)))
        self.assertEqual(Ledger.objects.count(), 2)
        self.assertEqual(LedgerEntry.objects.count(), 2)

    def test_amount_validation(self):
        """Ensure that credits are negative, debits are positive."""
        self.assertTrue(self.ACTION_CLASS.validate_amount(D(100)))
        self.assertTrue(self.ACTION_CLASS.validate_amount(D(0)))
        self.assertRaises(ValueError, self.ACTION_CLASS.validate_amount, D(-1))

    def test_multiple_entries_in_transaction(self):
        """Multiple LedgerEntries can be put into a single transaction."""
        with TransactionContext(
                self.creation_user, self.creation_user) as txn_1:
            txn_1.record(self.ACTION_CLASS(self.entity, D(100)))
        with TransactionContext(
                self.creation_user, self.creation_user) as txn_2:
            txn_2.record(self.ACTION_CLASS(self.entity, D(100)))
            txn_2.record(self.ACTION_CLASS(self.entity, D(10)))
        self.assertNotEqual(txn_1, txn_2)
        self.assertEqual(txn_2.transaction.entries.count(), 4)

    def _test_timestamp(self, timestamp):
        with TransactionContext(
                self.creation_user,
                self.creation_user,
                posted_timestamp=timestamp) as txn:
            txn.record(self.ACTION_CLASS(self.entity, D(100)))
        self.assertEqual(
            to_utc(txn.transaction.posted_timestamp), timestamp)
        txn = Transaction.objects.get(id=txn.transaction.id)
        self.assertEqual(
            to_utc(txn.posted_timestamp), timestamp)

    def test_fall_back_local(self):
        self._test_timestamp(self.fall_back_local)

    def test_fall_back_utc(self):
        self._test_timestamp(self.fall_back_utc)

    def test_spring_forward_local(self):
        self._test_timestamp(self.spring_forward_local)

    def test_spring_forward_utc(self):
        self._test_timestamp(self.spring_forward_utc)


class TestCharge(_TestLedgerActionBase):
    ACTION_CLASS = Charge


class TestPayment(_TestLedgerActionBase):
    ACTION_CLASS = Payment


class TestWriteDown(_TestLedgerActionBase):
    ACTION_CLASS = WriteDown


class TestRefund(_TestLedgerActionBase):
    ACTION_CLASS = Refund


class TestLedgerEntryAction(LedgerEntryActionSetUp):
    """
    Test Errors from LedgerEntryAction._get_debit_ledger and _get_credit_ledger
    """
    def test_not_implemented_errors(self):
        amount = D(100)

        with self.assertRaises(NotImplementedError):
            with TransactionContext(
                    self.creation_user, self.creation_user) as txn:
                txn.record(LedgerEntryAction(amount))

        ledger = Ledger.objects.last()

        with mock.patch.object(
                LedgerEntryAction, '_get_credit_ledger', return_value=ledger):
            with self.assertRaises(NotImplementedError):
                with TransactionContext(
                        self.creation_user, self.creation_user) as txn:
                    txn.record(LedgerEntryAction(amount))

        with mock.patch.object(
                LedgerEntryAction, '_get_credit_ledger', return_value=ledger):
            with mock.patch.object(
                    LedgerEntryAction,
                    '_get_debit_ledger',
                    return_value=ledger):
                with TransactionContext(
                        self.creation_user, self.creation_user) as txn:
                    txn.record(LedgerEntryAction(amount))


class TestTransferAction(LedgerEntryActionSetUp):
    def test_simple_transfer(self):
        amount = D(100)

        self.assertEqual(Transaction.objects.count(), 0)

        # First charge entity_1
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record(Charge(self.entity_1, amount))
        self.assertEqual(Transaction.objects.count(), 1)

        self.assertEqual(self.entity_1_ar_ledger.get_balance(), amount)
        self.assertEqual(self.entity_1_rev_ledger.get_balance(), -amount)

        # And transfer the entire balance to entity_2
        with TransactionContext(self.creation_user, self.creation_user)\
                as transfer_txn:
            transfer_txn.record(
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
            txn.record(Charge(self.entity_1, amount))
        with TransactionContext(self.creation_user, self.creation_user)\
                as transfer_txn:
            transfer_txn.record(
                TransferAmount(self.entity_1, self.entity_2, amount))

        # Void the charge
        void_txn = VoidTransaction(
            transfer_txn.transaction, self.creation_user).record()

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
            txn.record(Charge(self.entity_1, self.charge_amount))

        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record(Payment(self.entity_1, self.payment_amount))

    def test_refund(self):
        refund_amount = self.payment_amount - self.charge_amount
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record(Refund(self.entity_1, refund_amount))

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
            txn.record(Refund(self.entity_1, refund_amount))

        self.assertEqual(self.entity_1_ar_ledger.get_balance(),
                         self.charge_amount)
        self.assertEqual(self.entity_1_cash_ledger.get_balance(), D(0))
        # Revenue should be unchanged because it doesn't depend on actually
        # receiving payments
        self.assertEqual(self.entity_1_rev_ledger.get_balance(),
                         -1 * self.charge_amount)
