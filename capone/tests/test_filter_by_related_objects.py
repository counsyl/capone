from decimal import Decimal as D

import pytest

from capone.api.actions import create_transaction
from capone.api.actions import credit
from capone.api.actions import debit
from capone.models import LedgerEntry
from capone.models import MatchType
from capone.models import Transaction
from capone.tests.factories import LedgerFactory
from capone.tests.factories import OrderFactory
from capone.tests.factories import UserFactory


"""
Test Transaction.objects.filter_by_related_objects.
"""
AMOUNT = D('100')


@pytest.fixture
def create_transactions():
    create_user = UserFactory()
    ledger = LedgerFactory()

    def _create_transaction_with_evidence(evidence):
        return create_transaction(
            create_user,
            evidence=evidence,
            ledger_entries=[
                LedgerEntry(
                    ledger=ledger,
                    amount=credit(AMOUNT)),
                LedgerEntry(
                    ledger=ledger,
                    amount=debit(AMOUNT)),
            ]
        )

    order_1 = OrderFactory()
    order_2 = OrderFactory()

    transaction_with_both_orders = (
        _create_transaction_with_evidence([
            order_1,
            order_2,
        ])
    )
    transaction_with_only_order_1 = (
        _create_transaction_with_evidence([
            order_1,
        ])
    )
    transaction_with_only_order_2 = (
        _create_transaction_with_evidence([
            order_1,
        ])
    )
    transaction_with_neither_order = (
        _create_transaction_with_evidence([
            OrderFactory(),
        ])
    )

    transaction_with_three_orders = (
        _create_transaction_with_evidence([
            order_1,
            order_2,
            OrderFactory(),
        ])
    )

    return (
        order_1,
        order_2,
        transaction_with_both_orders,
        transaction_with_only_order_1,
        transaction_with_only_order_2,
        transaction_with_neither_order,
        transaction_with_three_orders,
        ledger,
    )


@pytest.mark.parametrize("match_type,queryset_function_name", [
    (MatchType.ANY, 'all'),
    (MatchType.ALL, 'all'),
    (MatchType.NONE, 'all'),
    (MatchType.EXACT, 'none'),
])
def test_filter_with_no_evidence(
    match_type, queryset_function_name, create_transactions,
):
    """
    Method returns correct Transactions with no evidence given.
    """
    result_queryset = getattr(
        Transaction.objects, queryset_function_name)().values_list('id')
    assert set(result_queryset) == set(
        Transaction.objects.filter_by_related_objects(
            [], match_type=match_type).values_list('id')
    )


@pytest.mark.parametrize("match_type,results", [
    (MatchType.ANY, [True, True, True, False, True]),
    (MatchType.ALL, [True, False, False, False, True]),
    (MatchType.NONE, [False, False, False, True, False]),
    (MatchType.EXACT, [True, False, False, False, False]),
])
def test_filters(match_type, results, create_transactions):
    """
    Method returns correct Transactions with various evidence given.

    This test uses the differing groups of transactions from
    `setUpTestData` to test that different `MatchTypes` give the right
    results.  Note that the list of booleans in the `parameterized.expand`
    decorator maps to the querysets in `query_list`.
    """
    (
        order_1,
        order_2,
        transaction_with_both_orders,
        transaction_with_only_order_1,
        transaction_with_only_order_2,
        transaction_with_neither_order,
        transaction_with_three_orders,
        ledger,
    ) = create_transactions

    query_list = [
        transaction_with_both_orders,
        transaction_with_only_order_1,
        transaction_with_only_order_2,
        transaction_with_neither_order,
        transaction_with_three_orders,
    ]

    for query, query_should_be_in_result in zip(query_list, results):
        if query_should_be_in_result:
            assert query in Transaction.objects.filter_by_related_objects(
                [order_1, order_2],
                match_type=match_type
            )
        else:
            assert query not in Transaction.objects.filter_by_related_objects(
                [order_1, order_2], match_type=match_type
            )


@pytest.mark.parametrize("match_type,query_counts", [
    (MatchType.ANY, 1),
    (MatchType.ALL, 1),
    (MatchType.NONE, 1),
    (MatchType.EXACT, 4),
])
def test_query_counts(
    match_type, query_counts, django_assert_num_queries, create_transactions,
):
    """
    `filter_by_related_objects` should use a constant number of queries.
    """
    (order_1, order_2, _, _, _, _, _, _) = create_transactions
    with django_assert_num_queries(query_counts):
        list(Transaction.objects.filter_by_related_objects(
            [order_1],
            match_type=match_type
        ))

    with django_assert_num_queries(query_counts):
        list(Transaction.objects.filter_by_related_objects(
            [order_1, order_2],
            match_type=match_type
        ))


def test_invalid_match_type():
    """
    Invalid MatchTypes are not allowed.
    """
    with pytest.raises(ValueError):
        Transaction.objects.filter_by_related_objects(match_type='foo')


def test_chaining_filter_to_existing_queryset(create_transactions):
    """
    `filter_by_related_objects` can be used like any other queryset filter.
    """
    (
        order_1,
        order_2,
        transaction_with_both_orders,
        transaction_with_only_order_1,
        transaction_with_only_order_2,
        transaction_with_neither_order,
        transaction_with_three_orders,
        ledger,
    ) = create_transactions

    assert Transaction.objects.count() == 5

    assert Transaction.objects.filter_by_related_objects(
        [order_1],
    ).count() == 4

    transactions_restricted_by_ledger = (
        Transaction.objects.filter(ledgers__in=[ledger])
    )

    assert transactions_restricted_by_ledger.filter_by_related_objects(
        [order_1]
    ).distinct().count() == 4
