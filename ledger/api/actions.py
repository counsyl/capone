"""Ledger actions are common operations that you'll probably want to perform.
"""
import itertools
from datetime import datetime
from functools import partial

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.db.transaction import atomic

from ledger.api.queries import validate_transaction
from ledger.models import Ledger
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LEDGER_CASH
from ledger.models import LEDGER_REVENUE
from ledger.models import LedgerBalance
from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.models import TransactionRelatedObject


class LedgerEntryAction(object):
    """A LedgerEntryAction is a common LedgerEntry-based operation."""
    def __init__(self, amount):
        super(LedgerEntryAction, self).__init__()
        try:
            self.validate_amount(amount)
        except ValueError:
            raise
        else:
            self.amount = amount

    @classmethod
    def validate_amount(cls, amount):
        """Validate the dollar amount for this action.

        Returns the validated amount or raises a ValueError.
        """
        if amount < 0:
            raise ValueError("Amounts must be non-negative")
        return True

    @atomic
    def get_ledger_entries(self):
        """Record debits and credits against an entity.

        Args:
            amount: The amount to charge the entity.
        """
        credit = LedgerEntry(
            ledger=self._get_credit_ledger(),
            amount=-self.amount,
            action_type=type(self).__name__)
        debit = LedgerEntry(
            ledger=self._get_debit_ledger(),
            amount=self.amount,
            action_type=type(self).__name__)
        return [credit, debit]

    def _get_credit_ledger(self):
        """Get the Ledger you want to use for credits.

        Returns a Ledger.
        """
        raise NotImplementedError("You must implement _get_credit_ledger")

    def _get_debit_ledger(self):
        """Get the Ledger you want to use for debits.

        Returns a Ledger.
        """
        raise NotImplementedError("You must implement _get_debit_ledger")


class SingleEntityLedgerEntryAction(LedgerEntryAction):
    def __init__(self, entity, amount):
        super(SingleEntityLedgerEntryAction, self).__init__(amount=amount)
        self.entity = entity

    def __repr__(self):
        return "<%s: %s %s>" % (type(self).__name__,
                                self.amount,
                                repr(self.entity))


class Charge(SingleEntityLedgerEntryAction):
    """Charge an entity a given amount."""
    def _get_credit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_REVENUE)
        return ledger

    def _get_debit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        return ledger


class Payment(SingleEntityLedgerEntryAction):
    """Record a payment from an entity."""
    def _get_credit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        return ledger

    def _get_debit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_CASH)
        return ledger


class Refund(SingleEntityLedgerEntryAction):
    """Record a payment to an entity (a refund)."""
    def _get_credit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_CASH)
        return ledger

    def _get_debit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        return ledger


class WriteDown(SingleEntityLedgerEntryAction):
    """Write down an amount.

    TODO: Should WriteDown allow us to go negative?
    """
    def _get_credit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        return ledger

    def _get_debit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_REVENUE)
        return ledger


class TransferAmount(LedgerEntryAction):
    """Transfer an amount from one entity's ledger to another."""
    def __init__(self, entity_from, entity_to, amount):
        super(TransferAmount, self).__init__(amount=amount)
        self.entity_from = entity_from
        self.entity_to = entity_to

    def __repr__(self):
        return "<%s: %s from %s to %s>" % (type(self).__name__,
                                           self.amount,
                                           repr(self.entity_from),
                                           repr(self.entity_to))

    @atomic
    def get_ledger_entries(self):
        entries = []
        for entry in itertools.chain(
                WriteDown(self.entity_from, self.amount).get_ledger_entries(),
                Charge(self.entity_to, self.amount).get_ledger_entries()):
            entry.action_type = type(self).__name__
            entries.append(entry)
        return entries


class TransactionContext(object):
    """Transactions manage FinancialActions."""
    @atomic
    def __init__(self, related_object, created_by, posted_timestamp=None,
                 secondary_related_objects=None):
        """Create a new transaction.

        Args:
            related_object: The object related to this Transaction,
                eg an Order.
            created_by: The User that initiated this Transaction.
            posted_timestamp: The time at which this transaction was
                posted. Defaults to now.
            secondary_related_objects: A list or queryset of other related
                objects you want to associate with this transaction.
        """
        if not posted_timestamp:
            posted_timestamp = datetime.now()
        posted_timestamp = posted_timestamp

        self.transaction = Transaction.objects.create_for_related_object(
            related_object,
            created_by=created_by,
            posted_timestamp=posted_timestamp)
        if secondary_related_objects:
            for robj in secondary_related_objects:
                TransactionRelatedObject.objects.create_for_object(
                    robj, transaction=self.transaction)

    @atomic
    def __enter__(self):
        return self

    @atomic
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.transaction.save()

    @atomic
    def record_action(self, action):
        """Record an Action in this Transaction.

        Args:
            action - A FinancialAction to include in this Transaction
        """
        ledger_entries = action.get_ledger_entries()
        for ledger_entry in ledger_entries:
            ledger_entry.transaction = self.transaction
        LedgerEntry.objects.bulk_create(ledger_entries)


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
    entries will be the same except have the opposite sense.

    If notes is not given, a default note will be set.

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
        raise Transaction.UnvoidableTransactionException(
            "Cannot void the same Transaction #({id}) more than once."
            .format(id=transaction.transaction_id))

    evidence = [
        tro.related_object for tro in transaction.related_objects.all()
    ]

    ledger_entries = [
        LedgerEntry(
            ledger=ledger_entry.ledger,
            amount=-ledger_entry.amount,
            action_type='VoidTransaction')
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

    if not type:
        type = Transaction.MANUAL

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
        type=type,
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
