from datetime import datetime
from decimal import Decimal as D

from django.db import IntegrityError
from django.test import TestCase

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import Charge
from ledger.api.actions import debit
from ledger.api.actions import Payment
from ledger.api.actions import TransactionContext
from ledger.api.actions import TransferAmount
from ledger.api.actions import void_transaction
from ledger.api.actions import WriteDown
from ledger.models import Ledger
from ledger.models import LedgerEntry
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
            txn.record_action(Charge(self.entity, amount))

        # Then void it
        void_txn = void_transaction(txn.transaction, self.creation_user)

        self.assertEqual(void_txn.voids, txn.transaction)

        self.assertEqual(self.entity_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_rev_ledger.get_balance(), D(0))

    def test_cant_void_twice(self):
        amount = D(100)
        # First record a charge
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record_action(Charge(self.entity, amount))

        # Then void it
        void_transaction(txn.transaction, self.creation_user)

        # Trying to void the same transaction again will not succeed
        self.assertRaises(
            Transaction.UnvoidableTransactionException,
            void_transaction, txn.transaction, self.creation_user)

    def test_can_void_void(self):
        # A void transaction can be voided, thus re-instating the original txn
        amount = D(100)
        # First record a charge
        with TransactionContext(self.creation_user, self.creation_user) as txn:
            txn.record_action(Charge(self.entity, amount))

        # Then void it
        void_txn = void_transaction(txn.transaction, self.creation_user)

        self.assertEqual(void_txn.voids, txn.transaction)

        # And void the void
        void_void_txn = (void_transaction(void_txn, self.creation_user))
        self.assertEqual(void_void_txn.voids, void_txn)

        self.assertEqual(self.entity_ar_ledger.get_balance(), amount)
        self.assertEqual(self.entity_rev_ledger.get_balance(), -amount)

    def test_void_multiple_charges(self):
        amount_1 = D(100)
        amount_2 = D(200)

        with TransactionContext(
                self.creation_user, self.creation_user) as txn_1:
            txn_1.record_action(Charge(self.entity, amount_1))
        with TransactionContext(
                self.creation_user, self.creation_user) as txn_2:
            txn_2.record_action(Charge(self.entity, amount_2))
        self.assertNotEqual(txn_1, txn_2)
        self.assertNotEqual(txn_1.transaction, txn_2.transaction)

        void_transaction(txn_1.transaction, self.creation_user)

        self.assertEqual(self.entity_ar_ledger.get_balance(), amount_2)
        self.assertEqual(self.entity_rev_ledger.get_balance(), -amount_2)

    def test_can_void_cash(self):
        # Cash transactions can be voided
        amount = D(100)

        with TransactionContext(
                self.creation_user, self.creation_user) as charge_txn:
            charge_txn.record_action(Charge(self.entity, amount))
        with TransactionContext(
                self.creation_user, self.creation_user) as pay_txn:
            pay_txn.record_action(Payment(self.entity, amount))

        # Void the charge
        void_transaction(charge_txn.transaction, self.creation_user)
        # And void the payment
        void_transaction(pay_txn.transaction, self.creation_user)
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
            txn.record_action(Charge(self.entity, charge_amount))

        with TransactionContext(
                self.creation_user, self.creation_user) as txn2:
            txn2.record_action(TransferAmount(
                self.entity, self.creation_user, transfer_amount))
            txn2.record_action(WriteDown(self.creation_user, comp_amount))

        self.assertEqual(self.creation_user_ar_ledger.get_balance(), D(99))
        self.assertEqual(self.entity_ar_ledger.get_balance(), D(200))

        void_transaction(txn2.transaction, self.creation_user)
        self.assertEqual(self.creation_user_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_ar_ledger.get_balance(), charge_amount)

    def test_void_from_create_transaction(self):
        amount = D(100)
        evidence = UserFactory.create_batch(3)
        transaction = create_transaction(
            user=UserFactory(),
            evidence=evidence,
            ledger_entries=[
                LedgerEntry(
                    ledger=self.entity_ar_ledger,
                    amount=credit(amount),
                ),
                LedgerEntry(
                    ledger=self.entity_cash_ledger,
                    amount=debit(amount),
                ),
            ],
        )
        self.assertEqual(self.entity_ar_ledger.get_balance(), credit(amount))
        self.assertEqual(self.entity_cash_ledger.get_balance(), debit(amount))
        voiding_transaction = void_transaction(transaction, self.creation_user)
        self.assertEqual(
            set(tro.related_object for tro
                in voiding_transaction.related_objects.all()),
            set(evidence),
        )
        self.assertEqual(self.entity_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_cash_ledger.get_balance(), D(0))
        self.assertEqual(voiding_transaction.voids, transaction)
        self.assertEqual(
            voiding_transaction.posted_timestamp,
            transaction.posted_timestamp)
        self.assertEqual(
            voiding_transaction.type,
            transaction.type)
        self.assertEqual(
            voiding_transaction.notes,
            'Voiding transaction {}'.format(transaction))

    def test_void_with_overridden_notes_and_type(self):
        amount = D(100)
        evidence = UserFactory.create_batch(3)
        transaction = create_transaction(
            user=UserFactory(),
            evidence=evidence,
            ledger_entries=[
                LedgerEntry(
                    ledger=self.entity_ar_ledger,
                    amount=credit(amount),
                ),
                LedgerEntry(
                    ledger=self.entity_cash_ledger,
                    amount=debit(amount),
                ),
            ],
            type=Transaction.AUTOMATIC,
        )
        voiding_transaction = void_transaction(
            transaction,
            self.creation_user,
            notes='test notes',
            type=Transaction.MANUAL)
        self.assertEqual(voiding_transaction.notes, 'test notes')
        self.assertEqual(voiding_transaction.type, Transaction.MANUAL)


class TestVoidTimestamps(TestVoidBase):
    def test_auto_timestamp(self):
        # If a posted_timestamp isn't specified we assume the posted_timestamp
        # is the same as the transaction we're voiding.
        amount = D(100)
        # First record a charge
        with TransactionContext(
                self.creation_user, self.creation_user) as charge_txn:
            charge_txn.record_action(Charge(self.entity, amount))

        # Then void it
        void_txn = void_transaction(charge_txn.transaction, self.creation_user)
        self.assertEqual(charge_txn.transaction.posted_timestamp,
                         void_txn.posted_timestamp)

    def test_given_timestamp(self):
        # If a posted_timestamp is given for the void, then use it
        amount = D(100)
        # First record a charge
        with TransactionContext(
                self.creation_user, self.creation_user) as charge_txn:
            charge_txn.record_action(Charge(self.entity, amount))

        # Then void it
        now = datetime.now()
        void_txn = void_transaction(
            charge_txn.transaction, self.creation_user,
            posted_timestamp=now)
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
            charge_txn.record_action(Charge(self.entity, D(100)))
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
            charge_txn.record_action(Charge(self.entity, D(100)))
        self.assertEqual(
            charge_txn.transaction.primary_related_object, self.user)
        self.assertEqual(
            set(charge_txn.transaction.secondary_related_objects),
            {self.user2, user3})


class TestExistingLedgerEntriesException(TestCase):
    def setUp(self):
        self.amount = D(100)
        self.user = UserFactory()

        self.accounts_receivable = Ledger.objects.get_or_create_ledger_by_name(
            'Accounts Receivable',
            increased_by_debits=True,
        )

        self.cash = Ledger.objects.get_or_create_ledger_by_name(
            'Cash',
            increased_by_debits=True,
        )

    def test_with_existing_ledger_entry(self):
        existing_transaction = create_transaction(
            self.user,
            ledger_entries=[
                LedgerEntry(
                    ledger=self.accounts_receivable,
                    amount=credit(self.amount)),
                LedgerEntry(
                    ledger=self.accounts_receivable,
                    amount=debit(self.amount)),
            ],
        )

        with self.assertRaises(Transaction.ExistingLedgerEntriesException):
            create_transaction(
                self.user,
                ledger_entries=list(existing_transaction.entries.all()),
            )
