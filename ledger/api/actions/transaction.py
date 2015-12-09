from datetime import datetime

from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.models import TransactionRelatedObject
from ledger.timezone import to_utc


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
                posted. Defaults to utcnow.
            secondary_related_objects: A list or queryset of other related
                objects you want to associate with this transaction.
        """
        if not posted_timestamp:
            posted_timestamp = datetime.utcnow()
        posted_timestamp = to_utc(posted_timestamp)

        self.transaction = Transaction.objects.create_for_related_object(
            related_object,
            created_by=created_by,
            _posted_timestamp=posted_timestamp)
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

    def record(self, action):
        """Record an Action in this Transaction.

        Args:
            action - A FinancialAction to include in this Transaction
        """
        self.transaction.entries.add(*action.get_ledger_entries())


class VoidTransaction(object):
    """Void a given Transaction.

    VoidTransactions are not enclosed in a TransactionContext, since they are
    really their own Transactions. It wouldn't make sense to allow other,
    non-voiding actions in a VoidTransaction because that transaction is
    marked as 'voiding' another, so it would break an assumption about
    the ledger entries contained.

    The do have a similar syntax to TransactionContext, though:

    with TransactionContext(related_object, created_by) as txn:
        txn.record(Charge(entity, 100))

    VoidTransaction(txn.transaction, created_by[, posted_timestamp]).record()

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
        self.posted_timestamp = to_utc(posted_timestamp)

    def get_ledger_entries(self):
        if not hasattr(self, 'context'):
            raise Transaction.UnvoidableTransactionException(
                "You can only use VoidTransaciton.record() to void "
                "transactions")

        entries = []
        for ledger_entry in self.other_transaction.entries.all():
            entries.append(LedgerEntry(
                ledger=ledger_entry.ledger,
                amount=-ledger_entry.amount,
                action_type=type(self).__name__))
        return entries

    def record(self):
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
        with TransactionContext(self.other_transaction.primary_related_object,
                            self.created_by,
                            posted_timestamp=self.posted_timestamp,
                            secondary_related_objects=self.other_transaction.
                            secondary_related_objects) as txn:
            txn.transaction.voids = self.other_transaction
            txn.transaction.notes = ("Voiding transaction %s" %
                                     self.other_transaction)
            self.context = txn
            txn.record(self)  # Will call self.get_ledger_entries()
            delattr(self, 'context')
        return txn.transaction
