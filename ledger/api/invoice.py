from collections import defaultdict
from datetime import datetime

from django.contrib.contenttypes.models import ContentType

from counsyl.product.ledger.models import InvoiceGenerationRecord
from counsyl.product.ledger.models import Ledger
from counsyl.product.ledger.timezone import to_utc


class Invoice(object):
    def __init__(self, entity, related_objects=None, timestamp=None,
                 creation_timestamp=None):
        """Instantiate an Invoice for a given entity.

        Args:
            entity: The Object, which has a Ledger, that you want to generate
                invoices for.
            related_objects: A queryset of objects of the same type, or a list
                of objects of different types. If not supplied, all objects
                in the requested time range will be considered.
            timestamp: The UTC time to filter Transactions by posted_timestamp.
                Defaults to datetime.utcnow().
            creation_timestamp: The UTC time to filter Transactions by
                creation_timestamp. This allows you to regenerate an Invoice
                from the past that doesn't include any recent, backdated,
                Transactions.
        """
        self.entity = entity
        self.related_objects = related_objects if related_objects else None
        self.ledger, created = Ledger.objects.get_or_create(
            type=Ledger.LEDGER_ACCOUNTS_RECEIVABLE,
            entity_content_type=ContentType.objects.get_for_model(entity),
            entity_id=entity.pk)
        if not timestamp:
            timestamp = datetime.utcnow()
        self.timestamp = to_utc(timestamp)
        if not creation_timestamp:
            creation_timestamp = datetime.utcnow()
        self.creation_timestamp = to_utc(creation_timestamp)
        InvoiceGenerationRecord.objects.create(
            _invoice_timestamp=timestamp,
            ledger=self.ledger,
            amount=self.amount)

    @property
    def amount(self):
        """Calculate the amount owed on this Invoice.

        Returns a Decimal for the amount currently owed.
        """
        return sum(entry.amount for entry in self.get_ledger_entries(False))

    def _exclude_voids(self, entries):
        """Exclude voided transactions from a queryset of LedgerEntries.

        In order to do this correctly one must find the cardinality of
        voids on a given transaction. If there are an odd number of voids,
        then the transaction is actually voided. If the cardinality is even,
        (eg the void is voided) then the transaction is not actually voided.

        TODO: Can this be optimized?
        """
        transactions = defaultdict(list)
        # Also order by transaction_id because void transactions reference
        # earlier transactions and need to be in the transactions dict
        entries_with_transactions = entries.select_related(
            'transaction', 'transaction__voids').order_by(
                'transaction___posted_timestamp', 'transaction__id')

        """
        This is clever:

        For entries that share a Transaction (eg, transfer & write down at
        the same time), the entries_with_transactions queryset will contain
        multiple instances of the shared Transaction. In order to calculate
        the cardinality of this Transaction correctly we have to maintain
        a separate count for each time it appears.

        To do this with a minimal amount of confusion all we need to do
        is keep a list of counts for the transaction, and push and pop
        the count accordingly. EG:

        Given this set up:

            with TransactionCtx(related_object, user) as txn:
                txn.record(Charge(entity_1, 1000))

            with TransactionCtx(related_object, user) as transfer_txn:
                transfer_txn.record(Transfer(entity_1, entity_2, 1000))
                transfer_txn.record(WriteDown(entity_2, 800))

        Now the list of LedgerEntries for entity_2 contains a Transfer and
        a WriteDown. Say we then voided example_txn.

            VoidTransaction(transfer_txn.transaction).record()

        Then entity_2's ledger entries are a Transfer, WriteDown, -Transfer,
        -WriteDown. Note the first two and the last two share transactions.

        If we want to exclude the voided leger entries from the list of
        entries, we can't just count the cardinality, because Transactions
        with an even number of entries might get erroneously excluded
        (this would happen for a void-void-void).

        Instead we need to keep a list of counts for each LedgerEntry that
        references this Transaction. We can do that by just appending 0
        onto the list of counts for the Transaction for each LedgerEntry. Then
        for Transactions with a voids pointer, we pop the first one off,
        increment it by one, and append it. Now a properly voided transaction
        should have a list of counts that are all odd numbers (and all the
        same) and a un-voided transaction should have a list of counts of
        all even numbers (that are all the same).
        """
        for entry in entries_with_transactions:
            txn = entry.transaction
            if txn.voids:
                ref = transactions[txn.voids]
                transactions[txn] = ref
                ref.append(ref.pop(0) + 1)
            else:
                transactions[txn].append(0)

        good_entries = set()
        for entry in entries_with_transactions:
            cardinality_set = set(transactions[entry.transaction])
            assert len(cardinality_set) == 1
            cardinality = cardinality_set.pop()
            if (cardinality % 2 == 0 and not entry.transaction.voids):
                good_entries.add(entry.id)
        return entries.filter(id__in=good_entries)

    def get_ledger_entries(self, exclude_voids=True):
        """Return a queryset of the ledger entries included in this Invoice.

        Args:
            exclude_voids: Whether or not to exclude void transactions from
                the list of ledger entries. Defaults to True.
        """
        entries = self.ledger.entries
        # First get those in the timestamp
        entries = entries.filter(
            transaction___posted_timestamp__lte=self.timestamp,
            transaction___creation_timestamp__lte=self.creation_timestamp)
        # And then filter by related objects
        entries = entries.filter_by_related_objects(self.related_objects)
        # Exclude voided transactions, if applicable
        if exclude_voids:
            entries = self._exclude_voids(entries)
        # And always order by time, oldest first
        entries = entries.order_by('transaction___posted_timestamp',
                                   'transaction__id')
        return entries

    def __eq__(self, other):
        return (self.ledger == other.ledger and
                self.timestamp == other.timestamp and
                self.creation_timestamp == other.creation_timestamp and
                (self.related_objects == other.related_objects
                 if not self.related_objects else
                 set(self.related_objects) == set(other.related_objects)) and
                (set(self.get_ledger_entries()) ==
                 set(other.get_ledger_entries())))
