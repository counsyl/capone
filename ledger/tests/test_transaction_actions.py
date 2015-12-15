from datetime import datetime
from decimal import Decimal as D

from django.db import IntegrityError
from django.test import TestCase

from ledger.api.actions import Charge
from ledger.api.actions import Payment
from ledger.api.actions import TransactionContext
from ledger.api.actions import EntityTransferAmount
from ledger.api.actions import VoidTransaction
from ledger.api.actions import WriteDown
from ledger.models import Ledger
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LEDGER_CASH
from ledger.models import LEDGER_REVENUE
from ledger.models import Transaction
from ledger.tests.factories import UserFactory


class TestVoidBase(TestCase):
    def setUp(self):
        self.entity = UserFactory()
        self.creation_user = UserFactory()
        self.entity_ar_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        self.entity_rev_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_REVENUE)
        self.entity_cash_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_CASH)
        self.creation_user_ar_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.creation_user, LEDGER_ACCOUNTS_RECEIVABLE)


class TestVoidTransaction(TestVoidBase):
    def test_simple_void(self):
        amount = D(100)
        # First record a charge
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record(Charge(self.entity, amount))

        # Then void it
        void_txn = VoidTransaction(
            txn.transaction, self.creation_user).record()

        self.assertEqual(void_txn.voids, txn.transaction)

        self.assertEqual(self.entity_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_rev_ledger.get_balance(), D(0))

    def test_cant_void_twice(self):
        amount = D(100)
        # First record a charge
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record(Charge(self.entity, amount))

        # Then void it
        VoidTransaction(txn.transaction, self.creation_user).record()

        # Trying to void the same transaction again will not succeed
        self.assertRaises(
            Transaction.UnvoidableTransactionException,
            VoidTransaction(txn.transaction, self.creation_user).record)

    def test_can_void_void(self):
        # A void transaction can be voided, thus re-instating the original txn
        amount = D(100)
        # First record a charge
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record(Charge(self.entity, amount))

        # Then void it
        void_txn = VoidTransaction(
            txn.transaction, self.creation_user).record()

        self.assertEqual(void_txn.voids, txn.transaction)

        # And void the void
        void_void_txn = VoidTransaction(void_txn, self.creation_user).record()
        self.assertEqual(void_void_txn.voids, void_txn)

        self.assertEqual(self.entity_ar_ledger.get_balance(), amount)
        self.assertEqual(self.entity_rev_ledger.get_balance(), -amount)

    def test_void_multiple_charges(self):
        amount_1 = D(100)
        amount_2 = D(200)

        with TransactionContext(
                self.creation_user, self.creation_user) as txn_1:
            txn_1.record(Charge(self.entity, amount_1))
        with TransactionContext(
                self.creation_user, self.creation_user) as txn_2:
            txn_2.record(Charge(self.entity, amount_2))
        self.assertNotEqual(txn_1, txn_2)
        self.assertNotEqual(txn_1.transaction, txn_2.transaction)

        VoidTransaction(txn_1.transaction, self.creation_user).record()

        self.assertEqual(self.entity_ar_ledger.get_balance(), amount_2)
        self.assertEqual(self.entity_rev_ledger.get_balance(), -amount_2)

    def test_can_void_cash(self):
        # Cash transactions can be voided
        amount = D(100)

        with TransactionContext(
                self.creation_user, self.creation_user) as charge_txn:
            charge_txn.record(Charge(self.entity, amount))
        with TransactionContext(
                self.creation_user, self.creation_user) as pay_txn:
            pay_txn.record(Payment(self.entity, amount))

        # Void the charge
        VoidTransaction(charge_txn.transaction, self.creation_user).record()
        # And void the payment
        VoidTransaction(pay_txn.transaction, self.creation_user).record()
        self.assertEqual(self.entity_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_rev_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_cash_ledger.get_balance(), D(0))

    def test_void_combined_transaction(self):
        # We can combine actions into a single transaction
        # For example:
        # 1. Charge $1000 to payer (Txn1)
        # 2. Transfer $800 to PT (Txn2)
        # 3. Comp PT $701 down to $99 (Txn2)
        # 4. Refile claim, so undo transfer (Txn3)
        #    Now Insurance owes $1000 and PT owes $0
        charge_amount = D(1000)
        transfer_amount = D(800)
        comp_amount = D(701)

        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record(Charge(self.entity, charge_amount))

        with TransactionContext(
                self.creation_user, self.creation_user) as txn2:
            txn2.record(EntityTransferAmount(
                self.entity, self.creation_user, transfer_amount))
            txn2.record(WriteDown(self.creation_user, comp_amount))

        self.assertEqual(self.creation_user_ar_ledger.get_balance(), D(99))
        self.assertEqual(self.entity_ar_ledger.get_balance(), D(200))

        VoidTransaction(txn2.transaction, self.creation_user).record()
        self.assertEqual(self.creation_user_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_ar_ledger.get_balance(), charge_amount)


class TestVoidTimestamps(TestVoidBase):
    def test_auto_timestamp(self):
        # If a posted_timestamp isn't specified we assume the posted_timestamp
        # is the same as the transaction we're voiding.
        amount = D(100)
        # First record a charge
        with TransactionContext(
                self.creation_user, self.creation_user) as charge_txn:
            charge_txn.record(Charge(self.entity, amount))

        # Then void it
        void_txn = VoidTransaction(
            charge_txn.transaction, self.creation_user).record()
        self.assertEqual(charge_txn.transaction.posted_timestamp,
                         void_txn.posted_timestamp)

    def test_given_timestamp(self):
        # If a posted_timestamp is given for the void, then use it
        amount = D(100)
        # First record a charge
        with TransactionContext(
                self.creation_user, self.creation_user) as charge_txn:
            charge_txn.record(Charge(self.entity, amount))

        # Then void it
        now = datetime.utcnow()
        void_txn = VoidTransaction(
            charge_txn.transaction, self.creation_user,
            posted_timestamp=now).record()
        self.assertEqual(now, void_txn.posted_timestamp)


class TestSecondaryRelatedObject(TestCase):
    def setUp(self):
        self.entity = UserFactory()
        self.user = UserFactory()
        self.user2 = UserFactory()
        self.ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity,
            LEDGER_ACCOUNTS_RECEIVABLE)

    def test_can_set_related_object(self):
        with TransactionContext(
                self.user, self.user,
                secondary_related_objects=[self.user2]) as charge_txn:
            charge_txn.record(Charge(self.entity, D(100)))
        self.assertEqual(
            charge_txn.transaction.primary_related_object, self.user)
        self.assertEqual(
            charge_txn.transaction.secondary_related_objects, [self.user2])

    def test_no_dupes_related_object(self):
        self.assertRaises(
            IntegrityError,
            TransactionContext,
            self.user, self.user,
            secondary_related_objects=[self.user2, self.user2])

    def test_multiple_secondary_objects(self):
        user3 = UserFactory()
        with TransactionContext(
                self.user, self.user,
                secondary_related_objects=[self.user2, user3]) as charge_txn:
            charge_txn.record(Charge(self.entity, D(100)))
        self.assertEqual(
            charge_txn.transaction.primary_related_object, self.user)
        self.assertEqual(
            set(charge_txn.transaction.secondary_related_objects),
            {self.user2, user3})


class TestFinalizedTransaction(TestVoidBase):
    def test_reentering_transaction_raises_error(self):
        amount = D(100)
        transaction = None
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            transaction = txn
            txn.record(Charge(self.entity, amount))

        with self.assertRaises(Transaction.UnmodifiableTransactionException):
            with transaction as txn:
                txn.record(Charge(self.entity, amount))
