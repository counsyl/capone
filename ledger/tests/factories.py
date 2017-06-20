from __future__ import unicode_literals
from decimal import Decimal

import factory
from django.contrib.auth import get_user_model

from capone.api.actions import create_transaction
from capone.api.actions import credit
from capone.api.actions import debit
from capone.models import Ledger
from capone.models import LedgerEntry
from capone.models import TransactionType
from capone.tests.models import CreditCardTransaction
from capone.tests.models import Order


class UserFactory(factory.DjangoModelFactory):
    """
    Factory for django.contrib.auth.get_user_model()

    `capone` relies on `django.contrib.auth` because each `Transaction` is
    attached to the `User` who created it.  Therefore, we can't just use a stub
    model here with, say, only a name field.
    """
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


class TransactionTypeFactory(factory.DjangoModelFactory):
    class Meta:
        model = TransactionType

    name = factory.Sequence(lambda n: "Transaction Type %s" % n)


def TransactionFactory(
    user=None,
    evidence=None,
    ledger_entries=None,
    notes='',
    type=None,
    posted_timestamp=None,
):
    """
    Factory for creating a Transaction

    Instead of inheriting from DjangoModelFactory, TransactionFactory is
    a method made to look like a factory call because the creation and
    validation of Transactions is handeled by `create_transaction`.
    """
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
        type=type or TransactionTypeFactory(),
        posted_timestamp=posted_timestamp,
    )
