import operator

from nose.tools import assert_equal

from ledger.models import Transaction


def assert_transaction_in_ledgers_for_amounts_with_evidence(
        ledger_amount_pairs,
        evidence,
        posted_timestamp=None,
        notes=None,
        type=None,
        user=None,
):
    """
    There is exactly one transaction with the given entries and evidence.

    The entries are specified as a list of (ledger name, amount) pairs.

    If posted_timestamp is given, the transaction's posted_timestamp
    is asserted equal to that value.
    """
    transactions_in_all_ledgers = reduce(
        operator.and_,
        (Transaction.objects.filter(ledgers__name=ledger)
         for ledger, _ in ledger_amount_pairs),
    )
    matching_transactions = (
        Transaction
        .objects
        .filter_by_related_objects(evidence)
        .filter(id__in=transactions_in_all_ledgers)
    )
    matching_transaction = matching_transactions.get()
    assert_equal(
        sorted(
            matching_transaction.entries.values_list(
                'ledger__name', 'amount')
        ),
        sorted(ledger_amount_pairs),
    )
    assert_equal(
        set(o.related_object
            for o in matching_transaction.related_objects.all()),
        set(evidence),
    )

    if posted_timestamp:
        assert_equal(matching_transaction.posted_timestamp, posted_timestamp)
