from __future__ import unicode_literals
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase

from capone.api.actions import credit
from capone.api.actions import debit
from capone.api.queries import assert_transaction_in_ledgers_for_amounts_with_evidence  # nopep8
from capone.models import Ledger
from capone.models import Transaction
from capone.tests.factories import CreditCardTransactionFactory
from capone.tests.factories import LedgerEntry
from capone.tests.factories import LedgerFactory
from capone.tests.factories import TransactionFactory
from capone.tests.factories import TransactionTypeFactory
from capone.tests.factories import UserFactory


class TestAssertTransactionInLedgersForAmountsWithEvidence(TestCase):
    def test_transaction_fields(self):
        """
        Test filtering by `posted_timestamp`, `notes`, `type`, and `user`.
        """
        time = datetime.now()
        wrong_time = datetime.now() - timedelta(days=1)
        user1 = UserFactory()
        user2 = UserFactory()
        credit_card_transaction = CreditCardTransactionFactory()
        ttype1 = TransactionTypeFactory(name='1')
        ttype2 = TransactionTypeFactory(name='2')

        FIELDS_TO_VALUES = [
            ('posted_timestamp', time, wrong_time),
            ('notes', 'foo', 'bar'),
            ('type', ttype1, ttype2),
            ('user', user1, user2),
        ]

        for field_name, right_value, wrong_value in FIELDS_TO_VALUES:
            TransactionFactory(
                evidence=[credit_card_transaction],
                **{field_name: right_value})
            ledger = Ledger.objects.last()
            assert_transaction_in_ledgers_for_amounts_with_evidence(
                ledger_amount_pairs=[
                    (ledger.name, credit(Decimal('100'))),
                    (ledger.name, debit(Decimal('100'))),
                ],
                evidence=[credit_card_transaction],
                **{field_name: right_value}
            )

    def test_no_matches(self):
        """
        No matching transaction raises DoesNotExist.
        """
        TransactionFactory()
        credit_card_transaction = CreditCardTransactionFactory()
        ledger = Ledger.objects.last()

        self.assertTrue(Transaction.objects.exists())

        with self.assertRaises(Transaction.DoesNotExist):
            assert_transaction_in_ledgers_for_amounts_with_evidence(
                ledger_amount_pairs=[
                    (ledger.name, credit(Decimal('100'))),
                    (ledger.name, debit(Decimal('100'))),
                ],
                evidence=[credit_card_transaction],
            )

    def test_multiple_matches(self):
        """
        Multiple matching transactions raises MultipleObjectsReturned.
        """
        credit_card_transaction = CreditCardTransactionFactory()
        amount = Decimal('100')
        ledger = LedgerFactory()
        for _ in range(2):
            TransactionFactory(
                UserFactory(),
                ledger_entries=[
                    LedgerEntry(amount=debit(amount), ledger=ledger),
                    LedgerEntry(amount=credit(amount), ledger=ledger),
                ],
                evidence=[credit_card_transaction],
            )

        self.assertEqual(Transaction.objects.count(), 2)

        with self.assertRaises(Transaction.MultipleObjectsReturned):
            assert_transaction_in_ledgers_for_amounts_with_evidence(
                ledger_amount_pairs=[
                    (ledger.name, credit(amount)),
                    (ledger.name, debit(amount)),
                ],
                evidence=[credit_card_transaction],
            )

    def test_mismatch_on_ledger_entries(self):
        """
        An otherwise matching Trans. will fail if its LedgerEntries mismatch.
        """
        credit_card_transaction = CreditCardTransactionFactory()
        amount = Decimal('100')
        ledger = LedgerFactory()
        evidence = [credit_card_transaction]

        TransactionFactory(
            UserFactory(),
            ledger_entries=[
                LedgerEntry(amount=debit(amount), ledger=ledger),
                LedgerEntry(amount=credit(amount), ledger=ledger),
            ],
            evidence=evidence,
        )

        with self.assertRaises(Transaction.DoesNotExist):
            assert_transaction_in_ledgers_for_amounts_with_evidence(
                ledger_amount_pairs=[
                    (ledger.name + 'foo', credit(amount)),
                    (ledger.name + 'foo', debit(amount)),
                ],
                evidence=evidence,
            )

        with self.assertRaises(AssertionError):
            assert_transaction_in_ledgers_for_amounts_with_evidence(
                ledger_amount_pairs=[
                    (ledger.name, credit(amount + Decimal('1'))),
                    (ledger.name, debit(amount + Decimal('1'))),
                ],
                evidence=evidence,
            )

    def test_mismatch_on_evidence(self):
        """
        An otherwise matching Trans. will fail if its evidence is different.
        """
        credit_card_transaction = CreditCardTransactionFactory()
        amount = Decimal('100')
        ledger = LedgerFactory()

        TransactionFactory(
            UserFactory(),
            ledger_entries=[
                LedgerEntry(amount=debit(amount), ledger=ledger),
                LedgerEntry(amount=credit(amount), ledger=ledger),
            ],
            evidence=[credit_card_transaction],
        )

        ledger_amount_pairs = [
            (ledger.name, credit(amount)),
            (ledger.name, debit(amount)),
        ]

        with self.assertRaises(Transaction.DoesNotExist):
            assert_transaction_in_ledgers_for_amounts_with_evidence(
                ledger_amount_pairs=ledger_amount_pairs,
                evidence=[
                    credit_card_transaction, CreditCardTransactionFactory()],
            )

        with self.assertRaises(Transaction.DoesNotExist):
            assert_transaction_in_ledgers_for_amounts_with_evidence(
                ledger_amount_pairs=ledger_amount_pairs,
                evidence=[],
            )
