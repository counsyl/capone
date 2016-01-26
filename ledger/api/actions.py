"""Ledger actions are common operations that you'll probably want to perform.
"""
import itertools
from datetime import datetime
from functools import partial

from django.conf import settings
from django.db.transaction import atomic

from ledger.models import Ledger
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LEDGER_CASH
from ledger.models import LEDGER_REVENUE
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
    def __init__(self, related_object, created_by, posted_timestamp=None,
                 secondary_related_objects=None):
        """Create a new transaction.

        Args:
            related_object: The object related to this Transaction,
                eg an Order.
            created_by: The User that initiated this Transaction.
            posted_timestamp: The UTC time at which this transaction was
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

    def __enter__(self):
        if self.transaction.finalized:
            raise Transaction.UnmodifiableTransactionException
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.transaction.finalized = True
        self.transaction.save()

    def record_action(self, action):
        """Record an Action in this Transaction.

        Args:
            action - A FinancialAction to include in this Transaction
        """
        self.transaction.entries.add(*action.get_ledger_entries())

    def record_entries(self, entries):
        """Record raw LedgerEntries: useful for cases not covered in api.actions

        Args:
            entries - An iterable of already-constructed LedgerEntry ORM
                objects to be added to this Transaction.  They are validated as
                having equal debits and credits, so that a Transaction will
                always balance.
        """
        self.transaction.entries.add(*entries)


class ReconciliationTransactionContext(TransactionContext):
    """
    A TransactionContext that produces a Recon Transaction
    """
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.transaction.type = Transaction.RECONCILIATION
        super(ReconciliationTransactionContext, self).__exit__(
            exc_type, exc_val, exc_tb)


class VoidTransaction(object):
    """Void a given Transaction.

    VoidTransactions are not enclosed in a TransactionContext, since they are
    really their own Transactions. It wouldn't make sense to allow other,
    non-voiding actions in a VoidTransaction because that transaction is
    marked as 'voiding' another, so it would break an assumption about
    the ledger entries contained.

    The do have a similar syntax to TransactionContext, though:

    with TransactionContext(related_object, created_by) as txn:
        txn.record_action(Charge(entity, 100))

    VoidTransaction(
        txn.transaction, created_by[, posted_timestamp]).record_action()

    It is assumed that the related_object must be the same as the transaction
    you're voiding.
    """
    def __init__(self, other_transaction, created_by, posted_timestamp=None):
        """Create a VoidTransaction.

        Args:
            other_transaction: The Transaction you want to void
            created_by: The user responsible for this void
            posted_timestamp: Optional timestamp for when this was posted.
                If none provided, then default to the posted_timestamp of
                the transaction we're voiding. If no timezone is attached
                to this timestamp, it is assumed to be naive UTC.
        """
        self.other_transaction = other_transaction
        self.created_by = created_by
        if not posted_timestamp:
            posted_timestamp = other_transaction.posted_timestamp
        self.posted_timestamp = posted_timestamp

    def get_ledger_entries(self):
        if not hasattr(self, 'context'):
            raise Transaction.UnvoidableTransactionException(
                "You can only use VoidTransaciton.record_action() to void "
                "transactions")

        entries = []
        for ledger_entry in self.other_transaction.entries.all():
            entries.append(LedgerEntry(
                ledger=ledger_entry.ledger,
                amount=-ledger_entry.amount,
                action_type=type(self).__name__))
        return entries

    def record_action(self):
        try:
            self.other_transaction.voided_by
        except Transaction.DoesNotExist:
            # Because OneToOne fields throw an exception instead of returning
            # None!
            pass
        else:
            raise Transaction.UnvoidableTransactionException(
                "Cannot void the same Transaction #({id}) more than once. "
                .format(id=self.other_transaction.transaction_id))

        # TODO: Should we be copying the secondary related objects here?
        with TransactionContext(
                self.other_transaction.primary_related_object,
                self.created_by,
                posted_timestamp=self.posted_timestamp,
                secondary_related_objects=self.other_transaction.
                secondary_related_objects) as txn:
            txn.transaction.voids = self.other_transaction
            txn.transaction.notes = ("Voiding transaction %s" %
                                     self.other_transaction)
            self.context = txn
            txn.record_action(self)  # Will call self.get_ledger_entries()
            delattr(self, 'context')
        return txn.transaction


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
