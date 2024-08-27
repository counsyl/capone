# -*- coding: utf-8 -*-
from decimal import Decimal

import pytest
from django.utils import timezone

from capone.api.actions import create_transaction
from capone.api.actions import credit
from capone.api.actions import debit
from capone.api.actions import void_transaction
from capone.exceptions import TransactionBalanceException
from capone.models import LedgerBalance
from capone.models import LedgerEntry
from capone.models import Transaction
from capone.tests.factories import CreditCardTransactionFactory
from capone.tests.factories import LedgerFactory
from capone.tests.factories import OrderFactory
from capone.tests.factories import TransactionFactory
from capone.tests.factories import TransactionTypeFactory
from capone.tests.factories import UserFactory


def test_unicode_methods():
    """
    Test all __str__ methods.
    """
    txn = TransactionFactory()

    tro = txn.related_objects.last()
    assert str(tro) == (
        'TransactionRelatedObject: CreditCardTransaction(id=%s)'
        % tro.related_object_id
    )

    entry = txn.entries.last()
    assert str(entry) == (
        "LedgerEntry: $%s in %s" % (
            entry.amount,
            entry.ledger.name,
        )
    )

    ledger = LedgerFactory(name='foo')
    assert str(ledger) == "Ledger foo"
    ledger = LedgerFactory(name='föo')
    assert str(ledger) == "Ledger föo"

    ttype = TransactionTypeFactory(name='foo')
    assert str(ttype) == "Transaction Type foo"

    balance = LedgerBalance.objects.last()
    assert str(balance) == (
        "LedgerBalance: %s for %s in %s" % (
            balance.balance,
            balance.related_object,
            balance.ledger,
        )
    )


def test_transaction_summary():
    """
    Test that Transaction.summary returns correct information.
    """
    ledger = LedgerFactory()
    amount = Decimal('500')
    ccx = CreditCardTransactionFactory()
    le1 = LedgerEntry(ledger=ledger, amount=credit(amount))
    le2 = LedgerEntry(ledger=ledger, amount=debit(amount))
    txn = TransactionFactory(
        evidence=[ccx],
        ledger_entries=[le1, le2]
    )

    assert txn.summary() == {
        'entries': [str(entry) for entry in txn.entries.all()],
        'related_objects': [
            'TransactionRelatedObject: CreditCardTransaction(id=%s)' %
            ccx.id,
        ],
    }


def test_setting_explicit_timestamp_field():
    transaction = TransactionFactory()
    old_posted_timestamp = transaction.posted_timestamp
    transaction.posted_timestamp = timezone.now()
    transaction.save()
    assert old_posted_timestamp != transaction.posted_timestamp


def test_editing_transactions():
    """
    Test that validation is still done when editing a Transaction.

    Limited editing is allowed on a Transaction, e.g. for changing notes.
    However, we want to make sure that our balance invariants are still kept
    when editing a Transaction.
    """
    transaction = TransactionFactory()

    transaction.notes = 'foo'
    transaction.save()

    entry = transaction.entries.last()
    entry.amount += Decimal('1')
    entry.save()

    with pytest.raises(TransactionBalanceException):
        transaction.save()


def test_non_void():
    """
    Test Transaction.objects.non_void filter.
    """

    order = OrderFactory()
    ar_ledger = LedgerFactory(name='A/R')
    cash_ledger = LedgerFactory(name='Cash')
    user = UserFactory()

    def add_transaction():
        return create_transaction(
            user,
            evidence=[order],
            ledger_entries=[
                LedgerEntry(
                    ledger=ar_ledger,
                    amount=credit(Decimal(50))),
                LedgerEntry(
                    ledger=cash_ledger,
                    amount=debit(Decimal(50))),
            ],
        )

    def filtered_out_by_non_void(transaction):
        """
        Return whether `transaction` is in `Transaction.objects.non_void()`.
        """
        queryset = Transaction.objects.filter(id=transaction.id)
        assert queryset.exists()
        return not queryset.non_void().exists()

    transaction_1 = add_transaction()
    assert not filtered_out_by_non_void(transaction_1)

    transaction_2 = add_transaction()
    assert not filtered_out_by_non_void(transaction_2)

    voiding_transaction = void_transaction(transaction_2, user)
    assert not filtered_out_by_non_void(transaction_1)
    assert filtered_out_by_non_void(transaction_2)
    assert filtered_out_by_non_void(voiding_transaction)
