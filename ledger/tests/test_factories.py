from datetime import datetime
from decimal import Decimal

from django.test import TestCase

from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.queries import assert_transaction_in_ledgers_for_amounts_with_evidence  # nopep8
from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.tests.factories import CreditCardTransactionFactory
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import TransactionFactory
from ledger.tests.factories import UserFactory
from ledger.tests.models import CreditCardTransaction


class TestTransactionFactory(TestCase):
    def test_no_args(self):
        TransactionFactory()

        ledger = Ledger.objects.last()
        assert_transaction_in_ledgers_for_amounts_with_evidence(
            ledger_amount_pairs=[
                (ledger.name, credit(Decimal('100'))),
                (ledger.name, debit(Decimal('100'))),
            ],
            evidence=[CreditCardTransaction.objects.get()],
        )

    def test_custom_ledger_entries(self):
        ledger = LedgerFactory()
        amount = Decimal('500')
        TransactionFactory(
            ledger_entries=[
                LedgerEntry(ledger=ledger, amount=credit(amount)),
                LedgerEntry(ledger=ledger, amount=debit(amount)),
            ]
        )

        assert_transaction_in_ledgers_for_amounts_with_evidence(
            ledger_amount_pairs=[
                (ledger.name, credit(amount)),
                (ledger.name, debit(amount)),
            ],
            evidence=[CreditCardTransaction.objects.get()],
        )

    def test_custom_evidence(self):
        ccx = CreditCardTransactionFactory()
        TransactionFactory(
            evidence=[ccx],
        )

        ledger = Ledger.objects.last()
        assert_transaction_in_ledgers_for_amounts_with_evidence(
            ledger_amount_pairs=[
                (ledger.name, credit(Decimal('100'))),
                (ledger.name, debit(Decimal('100'))),
            ],
            evidence=[ccx],
        )

    def test_custom_fields(self):
        """
        Test setting fields `posted_timestamp`, `notes`, `type`, and `user`.
        """
        time = datetime.now()
        FIELDS_TO_VALUES = [
            ('posted_timestamp', time),
            ('notes', 'booga'),
            ('type', Transaction.RECONCILIATION),
        ]

        for field_name, value in FIELDS_TO_VALUES:
            txn = TransactionFactory(**{field_name: value})
            self.assertEqual(getattr(txn, field_name), value)

        user = UserFactory()
        txn = TransactionFactory(user)
        self.assertEqual(txn.created_by, user)
