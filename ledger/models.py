"""Do NOT use Ledger models directly. Use ledger.actions instead."""
from collections import OrderedDict
from decimal import Decimal
from functools import partial

from counsyl_django_utils.models.non_deletable import NoDeleteManager
from counsyl_django_utils.models.non_deletable import NonDeletableModel
from django.conf import settings
try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import DateTimeField
from django.db.models import Q
from django.db.models import Sum
from django.db.models.query import QuerySet
from django.utils.translation import ugettext_lazy as _
from pytz import UTC
from uuidfield.fields import UUIDField

from ledger.timezone import to_utc


class ExplicitTimestampQuerysetMixin(QuerySet):
    timestamp_fields = ()

    def __init__(self, *args, **kwargs):
        super(ExplicitTimestampQuerysetMixin, self).__init__(*args, **kwargs)
        self.tz = UTC
        self.tz_name = 'utc'
        if not self.timestamp_fields:
            self.timestamp_fields = []
            # Let's introspect and do this for every timestamp
            for field in self.model._meta.fields:
                if isinstance(field, DateTimeField):
                    self.timestamp_fields.append(field.name)

    def annotate_with_explicit_timestamp(self):
        select_dict = OrderedDict()
        select_params = []
        for column in self.timestamp_fields:
            column_name = "%s_%s" % (column, self.tz_name)
            # Can't use select_params for `column` because it makes it a
            # sql string instead of a column select
            select_dict[column_name] = column + " at time zone %s"
            select_params.append(self.tz.zone)
        return self.extra(select=select_dict, select_params=select_params)


def explicit_timestamp_field(field_name, *args, **kwargs):
    def _set_timestamp_utc(self, attname, timestamp):
        """Set the given timestamp, assuming that we're being given a
        naive utc timestamp."""
        value = to_utc(timestamp)
        setattr(self, attname, value)
        setattr(self, "%s_utc" % attname, value.replace(tzinfo=None))

    def _get_timestamp_utc(self, attname):
        attname_utc = "%s_utc" % attname
        if not hasattr(self, attname_utc):
            setattr(self, attname_utc,
                    getattr(type(self)._default_manager.get(id=self.id),
                            attname_utc))
        return getattr(self, attname_utc)

    getter = partial(_get_timestamp_utc, attname=field_name)
    setter = partial(_set_timestamp_utc, attname=field_name)
    return property(getter, setter)


class InvoiceGenerationRecordQuerySet(
        ExplicitTimestampQuerysetMixin, QuerySet):
    pass


class InvoiceGenerationRecordManager(NoDeleteManager):
    def get_queryset(self):
        return InvoiceGenerationRecordQuerySet(self.model).\
            annotate_with_explicit_timestamp()


class InvoiceGenerationRecord(NonDeletableModel, models.Model):
    """An invoice is the amount owed at a given timestamp by a given entity.

    Invoices are recorded for historical reference. They should not be
    created directly. Instead you should go through ledger.invoice.Invoice.

    This is just a record of an Invoice being generated. It only serves to
    identify what ledger entries were included in an invoice sent out to
    a customer. It also allows a customer to look up their invoice by
    a unique ID.
    """
    objects = InvoiceGenerationRecordManager()

    creation_timestamp = explicit_timestamp_field('_creation_timestamp')
    _creation_timestamp = models.DateTimeField(
        _("UTC time this invoice was generated"),
        auto_now_add=True,
        db_index=True)
    invoice_timestamp = explicit_timestamp_field('_invoice_timestamp')
    _invoice_timestamp = models.DateTimeField(
        _("UTC time of the Invoice"),
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

    def get_for_objects(self, related_objects=None):
        """
        Get the TransactionRelatedObjects for an iterable of related_objects.

        Args:
            related_objects: A queryset of objects of the same type, or a list
                of objects of different types. If not supplied, all objects
                will be returned. If the given queryset is empty then no
                TransactionRelatedObjects will be returned.
        """
        if related_objects is None:
            return self
        elif not related_objects:
            return self.none()

        if isinstance(related_objects, models.Model):
            related_objects = [related_objects]

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


class TransactionQuerySet(ExplicitTimestampQuerysetMixin, QuerySet):
    def filter_by_related_objects(self, related_objects=None,
                                  require_all=True):
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

        if isinstance(related_objects, models.Model):
            related_objects = [related_objects]

        if require_all:
            qs = self
            ctypes = ContentType.objects.get_for_models(*related_objects)
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
        return TransactionQuerySet(self.model).\
            annotate_with_explicit_timestamp()

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
    creation_timestamp = explicit_timestamp_field('_creation_timestamp')
    _creation_timestamp = models.DateTimeField(
        _("UTC time this transaction was recorded locally"),
        auto_now_add=True,
        db_index=True)
    posted_timestamp = explicit_timestamp_field('_posted_timestamp')
    _posted_timestamp = models.DateTimeField(
        _("UTC time the transaction was posted"),
        null=False,
        db_index=True)

    finalized = models.BooleanField(
        _("Finalized transactions cannot be modified."),
        default=False)

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


class LedgerManager(NoDeleteManager):
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
            entity_id=entity.pk)

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
            entity_id=entity.pk)


class Ledger(NonDeletableModel, models.Model):
    """Ledgers are the record of debits and credits for a given entity."""
    objects = LedgerManager()
    transactions = models.ManyToManyField(Transaction, through='LedgerEntry')

    LEDGER_ACCOUNTS_RECEIVABLE = "ar"
    LEDGER_REVENUE = "revenue"
    LEDGER_CASH = "cash"
    LEDGER_CHOICES = (
        (LEDGER_ACCOUNTS_RECEIVABLE, "Accounts Receivable"),
        (LEDGER_REVENUE, "Revenue"),
        (LEDGER_CASH, "Cash")
    )
    type = models.CharField(
        _("The ledger type, eg Accounts Receivable, Revenue, etc"),
        choices=LEDGER_CHOICES, max_length=128)

    entity_content_type = models.ForeignKey(ContentType)
    entity_id = models.PositiveIntegerField(db_index=True)
    entity = GenericForeignKey('entity_content_type', 'entity_id')

    name = models.CharField(
        _("Name of this ledger"),
        max_length=255)

    class Meta:
        unique_together = ('type', 'entity_content_type', 'entity_id')

    def get_balance(self):
        """Get the current balance on this Ledger."""
        return self.entries.aggregate(balance=Sum('amount'))['balance']


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

    LedgerEntries must always be part of a transaction.
    """
    objects = LedgerEntryManager()

    ledger = models.ForeignKey(Ledger, related_name='entries')
    transaction = models.ForeignKey(Transaction, related_name='entries')

    entry_id = UUIDField(
        verbose_name=_("UUID for this ledger entry"),
        auto=True,
        version=4)

    amount = models.DecimalField(
        _("Amount of this entry."),
        help_text=_("Debits are positive, credits are negative."),
        max_digits=24, decimal_places=4)
    action_type = models.CharField(
        _("Type of action that created this LedgerEntry"),
        max_length=128, null=False, blank=True)

    def __unicode__(self):
        return u"LedgerEntry ({id}) {action} for ${amount}".format(
            id=self.entry_id, amount=self.amount, action=self.action_type)
