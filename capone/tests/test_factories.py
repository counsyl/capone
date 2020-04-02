from datetime import datetime
from decimal import Decimal

from django.test import TestCase

from capone.api.actions import credit
from capone.api.actions import debit
from capone.api.queries import assert_transaction_in_ledgers_for_amounts_with_evidence  # noqa: E501
from capone.models import Ledger
from capone.models import LedgerEntry
from capone.tests.factories import CreditCardTransactionFactory
from capone.tests.factories import LedgerFactory
from capone.tests.factories import TransactionFactory
from capone.tests.factories import TransactionTypeFactory
from capone.tests.factories import UserFactory


class TestTransactionFactory(TestCase):
    """
    Test TransactionFactory.

    We test this "factory" because it's actually a method implemented in this
    app, not a Factory Boy Factory.
    """
    @classmethod
    def setUpTestData(cls):
        cls.credit_card_transaction = CreditCardTransactionFactory()

    def test_no_args(self):
        TransactionFactory(evidence=[self.credit_card_transaction])

        ledger = Ledger.objects.last()
        assert_transaction_in_ledgers_for_amounts_with_evidence(
            ledger_amount_pairs=[
                (ledger.name, credit(Decimal('100'))),
                (ledger.name, debit(Decimal('100'))),
            ],
            evidence=[self.credit_card_transaction],
        )

    def test_custom_ledger_entries(self):
        ledger = LedgerFactory()
        amount = Decimal('500')
        TransactionFactory(
            evidence=[self.credit_card_transaction],
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
            evidence=[self.credit_card_transaction],
        )

    def test_custom_evidence(self):
        ccx = CreditCardTransactionFactory()
        TransactionFactory(evidence=[ccx])

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
            ('type', TransactionTypeFactory()),
            ('user', UserFactory()),
        ]

        for field_name, value in FIELDS_TO_VALUES:
            TransactionFactory(
                evidence=[self.credit_card_transaction],
                **{field_name: value})
            ledger = Ledger.objects.last()
            assert_transaction_in_ledgers_for_amounts_with_evidence(
                ledger_amount_pairs=[
                    (ledger.name, credit(Decimal('100'))),
                    (ledger.name, debit(Decimal('100'))),
                ],
                evidence=[self.credit_card_transaction],
                **{field_name: value}
            )
