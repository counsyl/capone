from datetime import datetime
from decimal import Decimal as D

from django.test import TestCase

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.actions import void_transaction
from ledger.exceptions import ExistingLedgerEntriesException
from ledger.exceptions import UnvoidableTransactionException
from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LEDGER_CASH
from ledger.models import LEDGER_REVENUE
from ledger.models import Transaction
from ledger.tests.factories import TransactionFactory
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
        txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.entity_ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.entity_rev_ledger),
        ])

        # Then void it
        void_txn = void_transaction(txn, self.creation_user)

        self.assertEqual(void_txn.voids, txn)

        self.assertEqual(self.entity_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_rev_ledger.get_balance(), D(0))

    def test_cant_void_twice(self):
        amount = D(100)
        # First record a charge
        txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.entity_ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.entity_rev_ledger),
        ])

        # Then void it
        void_transaction(txn, self.creation_user)

        # Trying to void the same transaction again will not succeed
        self.assertRaises(
            UnvoidableTransactionException,
            void_transaction, txn, self.creation_user)

    def test_can_void_void(self):
        # A void transaction can be voided, thus re-instating the original txn
        amount = D(100)
        # First record a charge
        txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.entity_ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.entity_rev_ledger),
        ])

        # Then void it
        void_txn = void_transaction(txn, self.creation_user)

        self.assertEqual(void_txn.voids, txn)

        # And void the void
        void_void_txn = (void_transaction(void_txn, self.creation_user))
        self.assertEqual(void_void_txn.voids, void_txn)

        self.assertEqual(self.entity_ar_ledger.get_balance(), amount)
        self.assertEqual(self.entity_rev_ledger.get_balance(), -amount)

    def test_void_multiple_charges(self):
        amount_1 = D(100)
        amount_2 = D(200)

        txn_1 = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount_1), ledger=self.entity_ar_ledger),
            LedgerEntry(
                amount=credit(amount_1), ledger=self.entity_rev_ledger),
        ])
        txn_2 = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount_2), ledger=self.entity_ar_ledger),
            LedgerEntry(
                amount=credit(amount_2), ledger=self.entity_rev_ledger),
        ])
        self.assertNotEqual(txn_1, txn_2)

        void_transaction(txn_1, self.creation_user)

        self.assertEqual(self.entity_ar_ledger.get_balance(), amount_2)
        self.assertEqual(self.entity_rev_ledger.get_balance(), -amount_2)

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
                    ledger=self.entity_rev_ledger,
                    amount=debit(amount),
                ),
            ],
        )
        self.assertEqual(self.entity_ar_ledger.get_balance(), credit(amount))
        self.assertEqual(self.entity_rev_ledger.get_balance(), debit(amount))
        voiding_transaction = void_transaction(transaction, self.creation_user)
        self.assertEqual(
            set(tro.related_object for tro
                in voiding_transaction.related_objects.all()),
            set(evidence),
        )
        self.assertEqual(self.entity_ar_ledger.get_balance(), D(0))
        self.assertEqual(self.entity_rev_ledger.get_balance(), D(0))
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
                    ledger=self.entity_rev_ledger,
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
        charge_txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.entity_ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.entity_rev_ledger),
        ])

        # Then void it
        void_txn = void_transaction(charge_txn, self.creation_user)
        self.assertEqual(charge_txn.posted_timestamp,
                         void_txn.posted_timestamp)

    def test_given_timestamp(self):
        # If a posted_timestamp is given for the void, then use it
        amount = D(100)
        # First record a charge
        charge_txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.entity_ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.entity_rev_ledger),
        ])

        # Then void it
        now = datetime.now()
        void_txn = void_transaction(
            charge_txn, self.creation_user,
            posted_timestamp=now)
        self.assertEqual(now, void_txn.posted_timestamp)


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

        with self.assertRaises(ExistingLedgerEntriesException):
            create_transaction(
                self.user,
                ledger_entries=list(existing_transaction.entries.all()),
            )
