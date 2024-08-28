from collections import defaultdict
from decimal import Decimal

import pytest
from django.db.models import F

from capone.api.actions import create_transaction
from capone.api.actions import credit
from capone.api.actions import debit
from capone.api.actions import void_transaction
from capone.api.queries import get_balances_for_object
from capone.models import Ledger
from capone.models import LedgerBalance
from capone.models import LedgerEntry
from capone.models import Transaction
from capone.tests.factories import LedgerFactory
from capone.tests.factories import OrderFactory
from capone.tests.factories import UserFactory
from capone.tests.models import Order
from capone.utils import rebuild_ledger_balances


"""
Test that `LedgerBalances` are automatically created and updated.
"""

amount = Decimal('50.00')


@pytest.fixture
def create_objects():
    order_1, order_2 = OrderFactory.create_batch(2)
    ar_ledger = LedgerFactory(name='A/R')
    cash_ledger = LedgerFactory(name='Cash')
    other_ledger = LedgerFactory(name='Other')
    user = UserFactory()

    yield (order_1, order_2, ar_ledger, cash_ledger, other_ledger, user)

    Transaction.objects.all().delete()
    (
        Ledger.objects
        .filter(id__in=(ar_ledger.id, cash_ledger.id))
        .delete()
    )
    order_1.delete()
    order_2.delete()
    user.delete()


def assert_objects_have_ledger_balances(other_ledger, object_ledger_balances):
    obj_to_ledger_balances = defaultdict(dict)

    for obj, ledger, balance in object_ledger_balances:
        if balance is not None:
            obj_to_ledger_balances[obj][ledger] = balance

    for obj, expected_balances in obj_to_ledger_balances.items():
        actual_balances = get_balances_for_object(obj)
        assert actual_balances == expected_balances
        assert other_ledger not in actual_balances
        assert actual_balances[other_ledger] == Decimal(0)


def test_no_balances(create_objects):
    (
        order_1,
        order_2,
        ar_ledger,
        cash_ledger,
        other_ledger,
        _,
    ) = create_objects
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, None),
            (order_1, cash_ledger, None),
            (order_2, ar_ledger, None),
            (order_2, cash_ledger, None),
        ]
    )


def test_ledger_balance_update(create_objects):
    (
        order_1,
        order_2,
        ar_ledger,
        cash_ledger,
        other_ledger,
        user,
    ) = create_objects

    def add_transaction(orders):
        return create_transaction(
            user,
            evidence=orders,
            ledger_entries=[
                LedgerEntry(
                    ledger=ar_ledger,
                    amount=credit(amount)),
                LedgerEntry(
                    ledger=cash_ledger,
                    amount=debit(amount)),
            ],
        )

    add_transaction([order_1])
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount)),
            (order_1, cash_ledger, debit(amount)),
            (order_2, ar_ledger, None),
            (order_2, cash_ledger, None),
        ]
    )

    add_transaction([order_2])
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount)),
            (order_1, cash_ledger, debit(amount)),
            (order_2, ar_ledger, credit(amount)),
            (order_2, cash_ledger, debit(amount)),
        ]
    )

    add_transaction([order_1])
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount) * 2),
            (order_1, cash_ledger, debit(amount) * 2),
            (order_2, ar_ledger, credit(amount)),
            (order_2, cash_ledger, debit(amount)),
        ]
    )

    transaction = add_transaction([order_1, order_2])
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount) * 3),
            (order_1, cash_ledger, debit(amount) * 3),
            (order_2, ar_ledger, credit(amount) * 2),
            (order_2, cash_ledger, debit(amount) * 2),
        ]
    )

    void_transaction(transaction, user)
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount) * 2),
            (order_1, cash_ledger, debit(amount) * 2),
            (order_2, ar_ledger, credit(amount)),
            (order_2, cash_ledger, debit(amount)),
        ]
    )


def test_rebuild_ledger_balance(create_objects, transactional_db):
    (
        order_1,
        order_2,
        ar_ledger,
        cash_ledger,
        other_ledger,
        user,
    ) = create_objects

    def add_transaction(orders):
        return create_transaction(
            user,
            evidence=orders,
            ledger_entries=[
                LedgerEntry(
                    ledger=ar_ledger,
                    amount=credit(amount)),
                LedgerEntry(
                    ledger=cash_ledger,
                    amount=debit(amount)),
            ],
        )

    rebuild_ledger_balances()
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, None),
            (order_1, cash_ledger, None),
            (order_2, ar_ledger, None),
            (order_2, cash_ledger, None),
        ]
    )

    add_transaction([order_1])
    rebuild_ledger_balances()
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount)),
            (order_1, cash_ledger, debit(amount)),
            (order_2, ar_ledger, None),
            (order_2, cash_ledger, None),
        ]
    )

    add_transaction([order_2])
    rebuild_ledger_balances()
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount)),
            (order_1, cash_ledger, debit(amount)),
            (order_2, ar_ledger, credit(amount)),
            (order_2, cash_ledger, debit(amount)),
        ]
    )

    add_transaction([order_1])
    rebuild_ledger_balances()
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount) * 2),
            (order_1, cash_ledger, debit(amount) * 2),
            (order_2, ar_ledger, credit(amount)),
            (order_2, cash_ledger, debit(amount)),
        ]
    )

    transaction = add_transaction([order_1, order_2])
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount) * 3),
            (order_1, cash_ledger, debit(amount) * 3),
            (order_2, ar_ledger, credit(amount) * 2),
            (order_2, cash_ledger, debit(amount) * 2),
        ]
    )

    void_transaction(transaction, user)
    rebuild_ledger_balances()
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount) * 2),
            (order_1, cash_ledger, debit(amount) * 2),
            (order_2, ar_ledger, credit(amount)),
            (order_2, cash_ledger, debit(amount)),
        ]
    )

    LedgerBalance.objects.update(balance=Decimal('1.00'))
    LedgerBalance.objects.first().delete()
    rebuild_ledger_balances()
    assert_objects_have_ledger_balances(
        other_ledger,
        [
            (order_1, ar_ledger, credit(amount) * 2),
            (order_1, cash_ledger, debit(amount) * 2),
            (order_2, ar_ledger, credit(amount)),
            (order_2, cash_ledger, debit(amount)),
        ]
    )


def test_ledger_balances_filtering(create_objects):
    (
        order_1,
        order_2,
        ar_ledger,
        cash_ledger,
        other_ledger,
        user,
    ) = create_objects

    def add_transaction(orders):
        return create_transaction(
            user,
            evidence=orders,
            ledger_entries=[
                LedgerEntry(
                    ledger=ar_ledger,
                    amount=credit(amount)),
                LedgerEntry(
                    ledger=cash_ledger,
                    amount=debit(amount)),
            ],
        )

    Order.objects.update(amount=amount * 2)

    def all_cash_orders():
        return set(
            Order.objects
            .filter(
                id__in=(order_1.id, order_2.id),
                ledger_balances__ledger=cash_ledger,
                ledger_balances__balance=F('amount'),
            )
        )

    assert all_cash_orders() == set()

    add_transaction([order_1])
    assert all_cash_orders() == set()

    add_transaction([order_1])
    assert all_cash_orders() == {order_1}

    add_transaction([order_2])
    assert all_cash_orders() == {order_1}

    add_transaction([order_2])
    assert all_cash_orders() == {order_1, order_2}
