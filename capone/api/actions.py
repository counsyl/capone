from __future__ import unicode_literals
from datetime import datetime
from functools import partial

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.db.transaction import atomic

from capone.api.queries import validate_transaction
from capone.exceptions import UnvoidableTransactionException
from capone.models import get_or_create_manual_transaction_type
from capone.models import Ledger
from capone.models import LedgerBalance
from capone.models import LedgerEntry
from capone.models import Transaction
from capone.models import TransactionRelatedObject


@atomic
def void_transaction(
    transaction,
    user,
    notes=None,
    type=None,
    posted_timestamp=None,
):
    """
    Create a new transaction that voids the given Transaction.

    The evidence will be the same as the voided Transaction. The ledger
    entries will be the same except have debits and credits swapped.

    If `notes` is not given, a default note will be set.

    If the posted_timestamp or type is not given, they will be the same
    as the voided Transaction.
    """
    try:
        transaction.voided_by
    except Transaction.DoesNotExist:
        # Because OneToOne fields throw an exception instead of returning
        # None!
        pass
    else:
        raise UnvoidableTransactionException(
            "Cannot void the same Transaction #({id}) more than once."
            .format(id=transaction.transaction_id))

    evidence = [
        tro.related_object for tro in transaction.related_objects.all()
    ]

    ledger_entries = [
        LedgerEntry(
            ledger=ledger_entry.ledger,
            amount=-ledger_entry.amount,
        )
        for ledger_entry in transaction.entries.all()
    ]

    if notes is None:
        notes = 'Voiding transaction {}'.format(transaction)

    if posted_timestamp is None:
        posted_timestamp = transaction.posted_timestamp

    if type is None:
        type = transaction.type

    voiding_transaction = create_transaction(
        evidence=evidence,
        ledger_entries=ledger_entries,
        notes=notes,
        posted_timestamp=posted_timestamp,
        type=type,
        user=user,
    )

    voiding_transaction.voids = transaction
    voiding_transaction.save()

    return voiding_transaction


def _credit_or_debit(amount, reverse):
    """
    Return the correctly signed `amount`, abiding by `DEBITS_ARE_NEGATIVE`

    This function is used to build `credit` and `debit`, which are convenience
    functions so that keeping credit and debit signs consistent is abstracted
    from the user.

    By default, debits should be positive and credits are negative, however
    `DEBITS_ARE_NEGATIVE` can be used to reverse this convention.
    """
    if amount < 0:
        raise ValueError(
            "Please express your Debits and Credits as positive numbers.")
    if getattr(settings, 'DEBITS_ARE_NEGATIVE', False):
        return amount if reverse else -amount
    else:
        return -amount if reverse else amount

credit = partial(_credit_or_debit, reverse=True)
debit = partial(_credit_or_debit, reverse=False)


@atomic
def create_transaction(
    user,
    evidence=(),
    ledger_entries=(),
    notes='',
    type=None,
    posted_timestamp=None,
):
    """
    Create a Transaction with LedgerEntries and TransactionRelatedObjects.

    This function is atomic and validates its input before writing to the DB.
    """
    # Lock the ledgers to which we are posting to serialize the update
    # of LedgerBalances.
    list(
        Ledger.objects
        .filter(id__in=(
            ledger_entry.ledger.id for ledger_entry in ledger_entries))
        .order_by('id')  # Avoid deadlocks.
        .select_for_update()
    )

    if not posted_timestamp:
        posted_timestamp = datetime.now()

    validate_transaction(
        user,
        evidence,
        ledger_entries,
        notes,
        type,
        posted_timestamp,
    )

    transaction = Transaction.objects.create(
        created_by=user,
        notes=notes,
        posted_timestamp=posted_timestamp,
        type=type or get_or_create_manual_transaction_type(),
    )

    for ledger_entry in ledger_entries:
        ledger_entry.transaction = transaction
        for related_object in evidence:
            content_type = ContentType.objects.get_for_model(related_object)
            num_updated = (
                LedgerBalance.objects
                .filter(
                    ledger=ledger_entry.ledger,
                    related_object_content_type=content_type,
                    related_object_id=related_object.id)
                .update(balance=F('balance') + ledger_entry.amount)
            )
            assert num_updated <= 1
            if num_updated == 0:
                # The first use of this evidence model in a ledger transaction.
                LedgerBalance.objects.create(
                    ledger=ledger_entry.ledger,
                    related_object_content_type=content_type,
                    related_object_id=related_object.id,
                    balance=ledger_entry.amount)

    LedgerEntry.objects.bulk_create(ledger_entries)

    transaction_related_objects = [
        TransactionRelatedObject(
            related_object=piece,
            transaction=transaction,
        )
        for piece in evidence
    ]
    TransactionRelatedObject.objects.bulk_create(transaction_related_objects)

    return transaction
