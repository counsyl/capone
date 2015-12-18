from collections import defaultdict
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from ledger.models import Transaction


def get_all_transactions_for_object(obj, ledgers=()):
    """
    Get all transactions for an object, optionally restricted by ledgers
    """
    transactions = (
        Transaction
        .objects
        .filter(
            related_objects__related_object_content_type=(
                ContentType.objects.get_for_model(obj)),
            related_objects__related_object_id=obj.id,
        )
        .distinct()
    )

    if ledgers:
        transactions = transactions.filter(ledger__in=ledgers)

    return transactions


def get_ledger_balances_for_transactions(transactions):
    balances = defaultdict(lambda: Decimal(0))

    for transaction in transactions:
        for entry in transaction.entries.all():
            balances[entry.ledger] += entry.amount

    return balances


def get_balances_for_object(obj):
    return get_ledger_balances_for_transactions(
        get_all_transactions_for_object(obj))
