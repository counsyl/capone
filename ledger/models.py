"""Do NOT use Ledger models directly. Use ledger.actions instead."""
from decimal import Decimal

from counsyl_django_utils.models.non_deletable import NoDeleteManager
from counsyl_django_utils.models.non_deletable import NonDeletableModel
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.db.models import Sum
from django.db.models.query import QuerySet
from django.utils.translation import ugettext_lazy as _
from uuidfield.fields import UUIDField


class InvoiceGenerationRecord(NonDeletableModel, models.Model):
    """A record of an invoice being generated at a particular time.

    An invoice is the amount owed at a given timestamp by a given entity.

    Invoices are recorded for historical reference. They should not be
    created directly. Instead you should go through ledger.invoice.Invoice.

    This is just a record of an Invoice being generated. It only serves to
    identify what ledger entries were included in an invoice sent out to
    a customer. It also allows a customer to look up their invoice by
    a unique ID.
    """
    creation_timestamp = models.DateTimeField(
        _("Time this invoice was generated"),
        auto_now_add=True,
        db_index=True)
    invoice_timestamp = models.DateTimeField(
        _("Time of the Invoice"),
        db_index=True)
    ledger = models.ForeignKey('Ledger')
    amount = models.DecimalField(
        _("Amount of this Invoice."),
        help_text=_("Money owed to us is positive. "
                    "Payments out are negative."),
        max_digits=24, decimal_places=4)


class TransactionRelatedObjectManager(NoDeleteManager):
    def create_for_object(self, related_object, **kwargs):
        kwargs['related_object_content_type'] = \
            ContentType.objects.get_for_model(related_object)
        kwargs['related_object_id'] = related_object.pk
        return self.create(**kwargs)

    def get_for_objects(self, related_objects=()):
        """
        Get the TransactionRelatedObjects for an iterable of related_objects.

        Args:
            related_objects: A queryset of objects of the same type, or a list
                of objects of different types. If not supplied, all objects
                will be returned. If the given queryset is empty then no
                TransactionRelatedObjects will be returned.
        """
        # content_types is a dict(model_instance -> ContentType)
        content_types = ContentType.objects.get_for_models(*related_objects)

        # Find all the TransactionRelatedObjects for the given related_objects
        qs = self.none()
        for related_object in related_objects:
            qs |= self.filter(
                Q(related_object_content_type=content_types[related_object],
                  related_object_id=related_object.id))
        return qs


class TransactionRelatedObject(NonDeletableModel, models.Model):
    objects = TransactionRelatedObjectManager()

    transaction = models.ForeignKey(
        'Transaction', related_name='related_objects')
    primary = models.BooleanField(
        _("Is this the primary related object?"),
        default=False)
    related_object_content_type = models.ForeignKey(ContentType)
    related_object_id = models.PositiveIntegerField(db_index=True)
    related_object = GenericForeignKey(
        'related_object_content_type', 'related_object_id')

    class Meta:
        unique_together = ('transaction', 'related_object_content_type',
                           'related_object_id')


class TransactionQuerySet(QuerySet):
    def filter_by_related_objects(self, related_objects=(), require_all=True):
        """Filter Transactions by arbitrary related objects.

        Args:
            related_objects: A queryset of objects of the same type, or a list
                of objects of different types. If not supplied, all objects
                will be returned. If the given queryset is empty then no
                Transactions will be returned.
            require_all: If True, then all related objects must be present
                in the Transaction's related objects list. Defaults to True.
        """
        if related_objects is None:
            return self
        elif not related_objects:
            return self.none()

        if require_all:
            qs = self
            ctypes = {
                related_object: ContentType.objects.get_for_model(related_object)  # nopep8
                for related_object in related_objects
            }
            for related_object in related_objects:
                ctype = ctypes[related_object]
                qs = qs.filter(
                    related_objects__related_object_content_type=ctype,
                    related_objects__related_object_id=related_object.id)
            return qs.distinct()
        else:
            # If we aren't requiring all related_objects to be in the set
            # of related objects for the returned object, then just find
            # all objects that have these related objects and filter out
            # the duplicates.
            related_objects_qs = (
                TransactionRelatedObject.objects.get_for_objects(
                    related_objects))
            return self.filter(
                related_objects__in=related_objects_qs).distinct('id')


class TransactionManager(NoDeleteManager):
    def create_for_related_object(self, related_object, **kwargs):
        transaction = self.create(**kwargs)
        TransactionRelatedObject.objects.create_for_object(
            related_object, primary=True, transaction=transaction)
        return transaction

    def get_queryset(self):
        return TransactionQuerySet(self.model)

    def filter_by_related_objects(self, related_objects=None, **kwargs):
        return self.get_queryset().filter_by_related_objects(
            related_objects, **kwargs)


class Transaction(NonDeletableModel, models.Model):
    """Transactions link together many LedgerEntries.

    A LedgerEntry cannot exist on its own, it must have an equal and opposite
    LedgerEntry (or set of LedgerEntries) that completely balance out.

    For accountability, all Transactions are required to have a user
    associated with them.
    """
    objects = TransactionManager()

    # By linking Transaction with Ledger with a M2M through LedgerEntry, we
    # have access to a Ledger's transactions *and* ledger entries through one
    # attribute per relation.
    ledgers = models.ManyToManyField('Ledger', through='LedgerEntry')

    transaction_id = UUIDField(
        verbose_name=_("UUID for this transaction"),
        auto=True,
        version=4)
    voids = models.OneToOneField(
        'Transaction',
        blank=True,
        null=True,
        related_name='voided_by')

    notes = models.TextField(
        _("Any notes to go along with this Transaction."),
        blank=True, null=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    creation_timestamp = models.DateTimeField(
        help_text=_("Time this transaction was recorded locally.  This field should *always* equal when this object was created."),  # nopep8
        auto_now_add=True,
        db_index=True)
    posted_timestamp = models.DateTimeField(
        help_text=_("Time the transaction was posted.  Change this field to model retroactive ledger entries."),  # nopep8
        null=False,
        db_index=True)

    finalized = models.BooleanField(
        _("Finalized transactions cannot be modified."),
        default=False)

    AUTOMATIC = 'Automatic'
    MANUAL = 'Manual'
    RECONCILIATION = 'Reconciliation'
    TRANSACTION_TYPE_CHOICES = (
        (AUTOMATIC, AUTOMATIC),
        (MANUAL, MANUAL),
        (RECONCILIATION, RECONCILIATION),
    )

    type = models.CharField(
        _("The type of transaction.  AUTOMATIC is for recurring tasks, and RECONCILIATION is for special Reconciliation transactions."),  # nopep8
        choices=TRANSACTION_TYPE_CHOICES,
        max_length=128,
        default=MANUAL,
    )

    @property
    def primary_related_object(self):
        """Get the primary related object for this Transaction."""
        return self.related_objects.get(primary=True).related_object

    @property
    def secondary_related_objects(self):
        """Get a list of the secondary related objects for this Transaction."""
        return [tro.related_object for tro in
                self.related_objects.exclude(primary=True)]

    def clean(self):
        self.validate()
        """
        TODO: I'd like to have this validation, but the Transaction must exist
            before it can have a related object. Ideas?
        if self.related_objects.filter(primary=True).count() == 0:
            raise Transaction.PrimaryRelatedObjectException(
                "You must supply a primary related object.")
        elif self.related_objects.filter(primary=True).count() > 1:
            raise Transaction.PrimaryRelatedObjectException(
                "There may only be one primary related object.")"""

    def validate(self):
        """Validates that this Transaction properly balances.

        A Transaction balances if its credit amounts match its debit amounts.
        If the Transaction does not balance, then a TransactionBalanceException
        is raised.

        Returns True if the Transaction validates.
        """
        total = sum(self.entries.values_list('amount', flat=True))
        if total != Decimal(0):
            raise Transaction.TransactionBalanceException(
                "Credits do not equal debits. Mis-match of %s." % total)
        return True

    def save(self, **kwargs):
        self.full_clean()
        super(Transaction, self).save(**kwargs)

    def __unicode__(self):
        return u"Transaction %s" % self.transaction_id

    class TransactionBalanceException(Exception):
        pass

    class UnvoidableTransactionException(Exception):
        pass

    class UnmodifiableTransactionException(Exception):
        pass

    class PrimaryRelatedObjectException(Exception):
        pass


LEDGER_ACCOUNTS_RECEIVABLE = "ar"
LEDGER_REVENUE = "revenue"
LEDGER_CASH = "cash"
LEDGER_CHOICES = (
    (LEDGER_ACCOUNTS_RECEIVABLE, "Accounts Receivable"),
    (LEDGER_REVENUE, "Revenue"),
    (LEDGER_CASH, "Cash")
)


class LedgerManager(NoDeleteManager):
    # The value of `increased_by_debits` for this type of account.
    ACCOUNT_TYPE_TO_INCREASED_BY_DEBITS = {
        LEDGER_ACCOUNTS_RECEIVABLE: True,
        LEDGER_REVENUE: False,
        LEDGER_CASH: True,
    }

    def get_or_create_ledger(self, entity, ledger_type):
        """Convenience method to get the correct ledger.

        Args:
            entity: The Entity to get a ledger for (InsurancePayer or
                    CustomerProfile)
            ledger_type: The appropriate Ledger.LEDGER_CHOICES
        """
        return Ledger.objects.get_or_create(
            type=ledger_type,
            entity_content_type=ContentType.objects.get_for_model(entity),
            entity_id=entity.pk,
            increased_by_debits=self.ACCOUNT_TYPE_TO_INCREASED_BY_DEBITS[
                ledger_type]
        )

    def get_ledger(self, entity, ledger_type):
        """Convenience method to get the correct ledger.

        Args:
            entity: The Entity to get a ledger for (InsurancePayer or
                    CustomerProfile)
            ledger_type: The appropriate Ledger.LEDGER_CHOICES
        """
        return Ledger.objects.get(
            type=ledger_type,
            entity_content_type=ContentType.objects.get_for_model(entity),
            entity_id=entity.pk,
            increased_by_debits=self.ACCOUNT_TYPE_TO_INCREASED_BY_DEBITS[
                ledger_type]
        )

    def get_or_create_ledger_by_name(self, name, increased_by_debits):
        return Ledger.objects.get_or_create(
            type='',
            entity_content_type=None,
            entity_id=None,
            name=name,
            increased_by_debits=increased_by_debits,
        )[0]


class Ledger(NonDeletableModel, models.Model):
    """Ledgers are the record of debits and credits for a given entity."""
    # Fields for object-attached Ledgers
    type = models.CharField(
        _("The ledger type, eg Accounts Receivable, Revenue, etc"),
        choices=LEDGER_CHOICES,
        max_length=128,
        # A blank `type` here means that the type of account represented by
        # this ledger is not of the types in LEDGER_CHOICES: it most likely has
        # a null `entity` and is a Counsyl-wide account like "Unreconciled
        # Cash".
        blank=True,
    )

    # The non-Ledger object that this Ledger is attached to.
    # TODO: Consider removing this GFK and moving its functionality to the
    # similar GFKs on Transaction.
    entity_content_type = models.ForeignKey(
        ContentType,
        blank=True,
        null=True,
    )
    entity_id = models.PositiveIntegerField(
        db_index=True,
        blank=True,
        null=True,
    )
    entity = GenericForeignKey(
        'entity_content_type',
        'entity_id',
    )

    # Fields for company-wide ledgers

    # TODO: Add field `ledger_number` here: Accounting likes to refer to
    # Ledgers via unique numbers that they can set when creating a Ledger.
    name = models.CharField(
        _("Name of this ledger"),
        unique=True,
        max_length=255)
    increased_by_debits = models.BooleanField(
        help_text="All accounts (and their corresponding ledgers) are of one of two types: either debits increase the value of an account or credits do.  By convention, asset and expense accounts are of the former type, while liabilities, equity, and revenue are of the latter.",  # nopep8
        default=None,
    )

    # Fields for both types of Ledgers

    objects = LedgerManager()

    class Meta:
        unique_together = ('type', 'entity_content_type', 'entity_id')

    def get_balance(self):
        """Get the current balance on this Ledger."""
        return self.entries.aggregate(balance=Sum('amount'))['balance']

    def __unicode__(self):
        return self.name or repr(self.entity)


class LedgerEntryQuerySet(QuerySet):
    def filter_by_related_objects(self, related_objects=None, **kwargs):
        """Filter LedgerEntries by arbitrary related objects.

        Args:
            related_objects: A queryset of objects of the same type, or a list
                of objects of different types. If not supplied, all objects
                will be returned.
        """
        # Because related_objects are stored on transactions, we'll have to
        # find all Transactions that reference the related objects, and then
        # filter down to only the LedgerEntries we want
        transactions = Transaction.objects.filter_by_related_objects(
            related_objects, **kwargs)
        return self.filter(transaction__in=transactions)


class LedgerEntryManager(NoDeleteManager):
    def get_queryset(self):
        return LedgerEntryQuerySet(self.model)

    def filter_by_related_objects(self, related_objects=None, **kwargs):
        return self.get_queryset().filter_by_related_objects(
            related_objects, **kwargs)


class LedgerEntry(NonDeletableModel, models.Model):
    """A single entry in a single column in a ledger.

    LedgerEntries must always be part of a transaction so that they balance
    according to double-entry bookkeeping.
    """
    class Meta:
        verbose_name_plural = "ledger entries"

    objects = LedgerEntryManager()

    ledger = models.ForeignKey(Ledger, related_name='entries')
    transaction = models.ForeignKey(Transaction, related_name='entries')

    entry_id = UUIDField(
        verbose_name=_("UUID for this ledger entry"),
        auto=True,
        version=4)

    amount = models.DecimalField(
        _("Amount of this entry."),
        max_digits=24, decimal_places=4)
    action_type = models.CharField(
        _("Type of action that created this LedgerEntry"),
        max_length=128, null=False, blank=True)

    def __unicode__(self):
        return u"LedgerEntry ({id}) {action} for ${amount}".format(
            id=self.entry_id, amount=self.amount, action=self.action_type)
