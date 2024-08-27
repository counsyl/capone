from decimal import Decimal as D

import pytest
from django.utils import timezone

from capone.api.actions import create_transaction
from capone.api.actions import credit
from capone.api.actions import debit
from capone.api.actions import void_transaction
from capone.exceptions import UnvoidableTransactionException
from capone.models import LedgerEntry
from capone.tests.factories import LedgerFactory
from capone.tests.factories import TransactionFactory
from capone.tests.factories import TransactionTypeFactory
from capone.tests.factories import UserFactory


amount = D(100)


@pytest.fixture
def create_objects():
    creation_user = UserFactory()
    ar_ledger = LedgerFactory()
    rev_ledger = LedgerFactory()
    creation_user_ar_ledger = LedgerFactory()
    ttype = TransactionTypeFactory()
    return (
        creation_user,
        ar_ledger,
        rev_ledger,
        creation_user_ar_ledger,
        ttype,
    )


def test_simple_void(create_objects):
    """
    Test voiding a `Transaction`.
    """
    (
        creation_user,
        ar_ledger,
        rev_ledger,
        creation_user_ar_ledger,
        ttype,
    ) = create_objects
    evidence = UserFactory.create_batch(3)
    transaction = create_transaction(
        user=UserFactory(),
        evidence=evidence,
        ledger_entries=[
            LedgerEntry(
                ledger=ar_ledger,
                amount=credit(amount),
            ),
            LedgerEntry(
                ledger=rev_ledger,
                amount=debit(amount),
            ),
        ],
    )
    assert ar_ledger.get_balance() == credit(amount)
    assert rev_ledger.get_balance() == debit(amount)
    voiding_transaction = void_transaction(transaction, creation_user)
    assert set(
        tro.related_object for tro in voiding_transaction.related_objects.all()
    ) == set(evidence)
    assert ar_ledger.get_balance() == D(0)
    assert rev_ledger.get_balance() == D(0)
    assert voiding_transaction.voids == transaction
    assert voiding_transaction.posted_timestamp == transaction.posted_timestamp
    assert voiding_transaction.type == transaction.type
    assert voiding_transaction.notes == 'Voiding transaction {}'.format(
        transaction,
    )


def test_void_with_non_default_type(create_objects):
    """
    Test voiding a `Transaction` with a non-default `type`.
    """
    (
        creation_user,
        ar_ledger,
        rev_ledger,
        creation_user_ar_ledger,
        ttype,
    ) = create_objects
    txn = TransactionFactory(creation_user, ledger_entries=[
        LedgerEntry(amount=debit(amount), ledger=ar_ledger),
        LedgerEntry(amount=credit(amount), ledger=rev_ledger),
    ])

    new_ttype = TransactionTypeFactory()
    void_txn = void_transaction(txn, creation_user, type=new_ttype)

    assert void_txn.voids == txn

    assert ar_ledger.get_balance() == D(0)
    assert rev_ledger.get_balance() == D(0)

    assert void_txn.type == new_ttype
    assert void_txn.type != txn.type


def test_cant_void_twice(create_objects):
    """
    Voiding a `Transaction` more than once is not permitted.
    """
    (
        creation_user,
        ar_ledger,
        rev_ledger,
        creation_user_ar_ledger,
        ttype,
    ) = create_objects
    txn = TransactionFactory(creation_user, ledger_entries=[
        LedgerEntry(amount=debit(amount), ledger=ar_ledger),
        LedgerEntry(amount=credit(amount), ledger=rev_ledger),
    ])

    void_transaction(txn, creation_user)

    pytest.raises(
        UnvoidableTransactionException,
        void_transaction,
        txn,
        creation_user,
    )


def test_can_void_void(create_objects):
    """
    A void can be voided, thus restoring the original transaction.
    """
    (
        creation_user,
        ar_ledger,
        rev_ledger,
        creation_user_ar_ledger,
        ttype,
    ) = create_objects
    txn = TransactionFactory(creation_user, ledger_entries=[
        LedgerEntry(amount=debit(amount), ledger=ar_ledger),
        LedgerEntry(amount=credit(amount), ledger=rev_ledger),
    ])

    void_txn = void_transaction(txn, creation_user)

    assert void_txn.voids == txn

    void_void_txn = (void_transaction(void_txn, creation_user))
    assert void_void_txn.voids == void_txn

    assert ar_ledger.get_balance() == amount
    assert rev_ledger.get_balance() == -amount


def test_void_with_overridden_notes_and_type(create_objects):
    """
    Test voiding while setting notes and type.
    """
    (
        creation_user,
        ar_ledger,
        rev_ledger,
        creation_user_ar_ledger,
        ttype,
    ) = create_objects
    evidence = UserFactory.create_batch(3)
    transaction = create_transaction(
        user=UserFactory(),
        evidence=evidence,
        ledger_entries=[
            LedgerEntry(
                ledger=ar_ledger,
                amount=credit(amount),
            ),
            LedgerEntry(
                ledger=rev_ledger,
                amount=debit(amount),
            ),
        ],
        type=ttype,
    )
    voiding_transaction = void_transaction(
        transaction,
        creation_user,
        notes='test notes',
    )
    assert voiding_transaction.notes == 'test notes'
    assert voiding_transaction.type == transaction.type


def test_auto_timestamp(create_objects):
    """
    If a posted_timestamp isn't specified we assume the posted_timestamp is
    the same as the transaction we're voiding.
    """
    (
        creation_user,
        ar_ledger,
        rev_ledger,
        creation_user_ar_ledger,
        ttype,
    ) = create_objects
    charge_txn = TransactionFactory(creation_user, ledger_entries=[
        LedgerEntry(amount=debit(amount), ledger=ar_ledger),
        LedgerEntry(amount=credit(amount), ledger=rev_ledger),
    ])

    void_txn = void_transaction(charge_txn, creation_user)
    assert charge_txn.posted_timestamp == void_txn.posted_timestamp


def test_given_timestamp(create_objects):
    """
    If a posted_timestamp is given for the void, then use it
    """
    (
        creation_user,
        ar_ledger,
        rev_ledger,
        creation_user_ar_ledger,
        ttype,
    ) = create_objects
    charge_txn = TransactionFactory(creation_user, ledger_entries=[
        LedgerEntry(amount=debit(amount), ledger=ar_ledger),
        LedgerEntry(amount=credit(amount), ledger=rev_ledger),
    ])

    now = timezone.now()
    void_txn = void_transaction(
        charge_txn, creation_user,
        posted_timestamp=now)
    assert now == void_txn.posted_timestamp
