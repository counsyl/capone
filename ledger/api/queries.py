import operator
from collections import defaultdict
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from nose.tools import assert_equal

from ledger.exceptions import ExistingLedgerEntriesException
from ledger.exceptions import NoLedgerEntriesException
from ledger.exceptions import TransactionBalanceException
from ledger.models import LedgerBalance
from ledger.models import MatchType
from ledger.models import Transaction


def get_balances_for_object(obj):
    """
    Return a dict from Ledger to Decimal for an evidence model.

    The dict maps the ledgers for which the model has matching
    ledger entries to the ledger balance amount for the model
    in that ledger.

    The dict is a `defaultdict` which will return Decimal(0)
    when looking up the balance of a ledger for which the model
    has no associated transactions.
    """
    balances = defaultdict(lambda: Decimal(0))
    content_type = ContentType.objects.get_for_model(obj)
    ledger_balances = (
        LedgerBalance
        .objects
        .filter(
            related_object_content_type=content_type,
            related_object_id=obj.id)
    )
    for ledger_balance in ledger_balances:
        balances[ledger_balance.ledger] = ledger_balance.balance
    return balances


def validate_transaction(
    user,
    evidence=(),
    ledger_entries=(),
    notes=None,
    type=None,
    posted_timestamp=None,
):
    """
    Validates a Transaction and its sub-models before saving.

    One, it validates that this Transaction properly balances.

    A Transaction balances if its credit amounts match its debit amounts.
    If the Transaction does not balance, then a TransactionBalanceException
    is raised.

    Two, it checks that the Transaction has entries in it.  We do not allow
    empty Transactions.

    Three, it checks that the ledger entries are new, unsaved models.
    """
    total = sum([entry.amount for entry in ledger_entries])
    if total != Decimal(0):
        raise TransactionBalanceException(
            "Credits do not equal debits. Mis-match of %s." % total)

    if not ledger_entries:
        raise NoLedgerEntriesException("Transaction has no entries.")

    for ledger_entry in ledger_entries:
        if ledger_entry.pk is not None:
            raise ExistingLedgerEntriesException("LedgerEntry already exists.")


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
    matching_transaction = (
        Transaction
        .objects
        .filter(id__in=transactions_in_all_ledgers)
        .filter_by_related_objects(evidence, match_type=MatchType.EXACT)
        .get()
    )
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
