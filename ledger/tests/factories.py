from decimal import Decimal

import factory  # FactoryBoy
from django.contrib.auth import get_user_model

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.tests.models import CreditCardTransaction
from ledger.tests.models import Order


class UserFactory(factory.DjangoModelFactory):
    """Create User instances with monotonically increasing usernames."""
    class Meta:
        model = get_user_model()
    email = username = factory.Sequence(lambda n: "TransactionUser #%s" % n)


class LedgerFactory(factory.DjangoModelFactory):
    class Meta:
        model = Ledger

    increased_by_debits = True
    name = factory.Sequence(lambda n: 'Test Ledger {}'.format(n))
    number = factory.Sequence(lambda n: n)


class OrderFactory(factory.DjangoModelFactory):
    class Meta:
        model = Order

    patient_name = factory.Sequence(lambda n: "Patient %s" % n)
    barcode = factory.Sequence(lambda n: str(n))


class CreditCardTransactionFactory(factory.DjangoModelFactory):
    class Meta:
        model = CreditCardTransaction

    cardholder_name = factory.Sequence(lambda n: "Cardholder %s" % n)


def TransactionFactory(
    user=None,
    evidence=None,
    ledger_entries=None,
    notes='',
    type=None,
    posted_timestamp=None,
):
    if user is None:
        user = UserFactory()

    if evidence is None:
        evidence = [CreditCardTransactionFactory()]

    if ledger_entries is None:
        ledger = LedgerFactory()
        amount = Decimal('100')
        ledger_entries = [
            LedgerEntry(
                ledger=ledger,
                amount=debit(amount),
            ),
            LedgerEntry(
                ledger=ledger,
                amount=credit(amount),
            ),
        ]

    return create_transaction(
        user,
        evidence=evidence,
        ledger_entries=ledger_entries,
        notes=notes,
        type=type,
        posted_timestamp=posted_timestamp,
    )
