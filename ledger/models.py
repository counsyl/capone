import operator
import uuid
from decimal import Decimal
from enum import Enum

from counsyl_django_utils.models.non_deletable import NoDeleteManager
from counsyl_django_utils.models.non_deletable import NonDeletableModel
from counsyl_django_utils.models.non_deletable import NonDeletableQuerySet
from counsyl_django_utils.models.timestamped import TimeStampedModel
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.db.models import Sum
from django.utils.translation import ugettext_lazy as _

from ledger.exceptions import TransactionBalanceException


POSITIVE_DEBITS_HELP_TEXT = "Amount for this entry.  Debits are positive, and credits are negative."  # nopep8
NEGATIVE_DEBITS_HELP_TEXT = "Amount for this entry.  Debits are negative, and credits are positive."  # nopep8


class TransactionRelatedObject(NonDeletableModel, models.Model):
    """
    A piece of evidence for a particular Transaction.

    TransactionRelatedObject has a FK to a Transaction and a GFK that can point
    to any object in the database.  We create as many TransactionRelatedObjects
    as there are pieces of evidence.
    """
    class Meta:
        unique_together = ('transaction', 'related_object_content_type',
                           'related_object_id')

    transaction = models.ForeignKey(
        'Transaction',
        related_name='related_objects')
    related_object_content_type = models.ForeignKey(
        ContentType)
    related_object_id = models.PositiveIntegerField(
        db_index=True)
    related_object = GenericForeignKey(
        'related_object_content_type',
        'related_object_id')

    def __unicode__(self):
        return "TransactionRelatedObject: %s(id=%d)" % (
            self.related_object_content_type.model_class().__name__,
            self.related_object_id)


class MatchType(Enum):
    ANY = 'any'
    ALL = 'all'
    NONE = 'none'
    EXACT = 'exact'


class TransactionQuerySet(NonDeletableQuerySet):
    def non_void(self):
        return self.filter(
            voided_by__isnull=True,
            voids__isnull=True,
        )

    def filter_by_related_objects(
            self, related_objects=(), match_type=MatchType.ALL):
        """
        Filter Transactions to only those with related_objects as evidence.

        This filter takes an option, `match_type` that controls how the
        matching to `related_objects` is construed:

        -   ANY: Return Transactions that have *any* of the objects in
            `related_objects` as evidence.
        -   ALL: Return Transactions that have *all* of the objects in
            `related_objects` as evidence: they can have other evidence
            objects, but they must have all of `related_objects` (c.f. EXACT).
        -   NONE: Return only those Transactions that have *none* of
            `related_objects` as evidence.  They may have other evidence.
        -   EXACT: Return only those Transactions whose evidence matches
            `related_objects` *exactly*: they may not have other evidence (c.f.
            ALL).

        The current implementation of EXACT is not as performant as the other
        options, so be careful using it with large numbers of
        `related_objects`.
        """
        content_types = ContentType.objects.get_for_models(
            *related_objects)

        if match_type == MatchType.ANY:
            combined_query = reduce(
                operator.or_,
                [
                    Q(
                        related_objects__related_object_content_type=(
                            content_types[related_object]),
                        related_objects__related_object_id=related_object.id,
                    )
                    for related_object in related_objects
                ],
                Q(),
            )
            return self.filter(combined_query).distinct()
        elif match_type == MatchType.ALL:
            for related_object in related_objects:
                self = self.filter(
                    related_objects__related_object_content_type=(
                        content_types[related_object]),
                    related_objects__related_object_id=related_object.id,
                )
            return self
        elif match_type == MatchType.NONE:
            for related_object in related_objects:
                self = self.exclude(
                    related_objects__related_object_content_type=(
                        content_types[related_object]),
                    related_objects__related_object_id=related_object.id,
                )
            return self
        elif match_type == MatchType.EXACT:
            for related_object in related_objects:
                self = (
                    self
                    .filter(
                        related_objects__related_object_content_type=(
                            content_types[related_object]),
                        related_objects__related_object_id=related_object.id,
                    )
                    .prefetch_related(
                        'related_objects__related_object',
                    )
                )

            exact_matches = []
            for matched in self:
                matched_objects = {
                    m.related_object for m in matched.related_objects.all()}
                if matched_objects == set(related_objects):
                    exact_matches.append(matched.id)
            return self.filter(id__in=exact_matches)
        else:
            raise ValueError("Invalid match_type.")


class Transaction(NonDeletableModel, models.Model):
    """
    Transactions link together many LedgerEntries.

    A LedgerEntry cannot exist on its own, it must have an equal and opposite
    LedgerEntry (or set of LedgerEntries) that completely balance out.

    For accountability, all Transactions are required to have a user
    associated with them.
    """
    # By linking Transaction with Ledger with a M2M through LedgerEntry, we
    # have access to a Ledger's transactions *and* ledger entries through one
    # attribute per relation.
    ledgers = models.ManyToManyField(
        'Ledger',
        through='LedgerEntry')

    transaction_id = models.UUIDField(
        help_text=_("UUID for this transaction"),
        default=uuid.uuid4)
    voids = models.OneToOneField(
        'Transaction',
        blank=True,
        null=True,
        related_name='voided_by')

    notes = models.TextField(
        help_text=_("Any notes to go along with this Transaction."),
        blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL)
    creation_timestamp = models.DateTimeField(
        help_text=_("Time this transaction was recorded locally.  This field should *always* equal when this object was created."),  # nopep8
        auto_now_add=True,
        db_index=True)
    posted_timestamp = models.DateTimeField(
        help_text=_("Time the transaction was posted.  Change this field to model retroactive ledger entries."),  # nopep8
        db_index=True)

    AUTOMATIC = 'Automatic'
    MANUAL = 'Manual'
    RECONCILIATION = 'Reconciliation'
    TRANSACTION_TYPE_CHOICES = (
        (AUTOMATIC, AUTOMATIC),
        (MANUAL, MANUAL),
        (RECONCILIATION, RECONCILIATION),
    )

    type = models.CharField(
        help_text=_("The type of transaction.  AUTOMATIC is for recurring tasks, and RECONCILIATION is for special Reconciliation transactions."),  # nopep8
        choices=TRANSACTION_TYPE_CHOICES,
        max_length=128,
        default=MANUAL,
    )

    objects = TransactionQuerySet.as_manager()

    def clean(self):
        self.validate()

    def validate(self):
        """
        Validates that this Transaction properly balances.

        This method is not as thorough as
        `ledger.api.queries.validate_transaction` because not all of the
        validations in that file apply to an already-created object.  Instead,
        the only check that makes sense is that the entries for the transaction
        still balance.
        """
        total = sum(self.entries.values_list('amount', flat=True))
        if total != Decimal(0):
            raise TransactionBalanceException(
                "Credits do not equal debits. Mis-match of %s." % total)
        return True

    def save(self, **kwargs):
        self.full_clean()
        super(Transaction, self).save(**kwargs)

    def __unicode__(self):
        return u"Transaction %s" % self.transaction_id

    def summary(self):
        """
        Return summary of Transaction, suitable for the CLI or a changelist.
        """
        return {
            'entries':
            [unicode(entry) for entry in self.entries.all()],
            'related_objects':
            [unicode(obj) for obj in self.related_objects.all()],
        }


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
        try:
            return Ledger.objects.get(
                type=ledger_type,
                entity_content_type=ContentType.objects.get_for_model(entity),
                entity_id=entity.pk,
                increased_by_debits=self.ACCOUNT_TYPE_TO_INCREASED_BY_DEBITS[
                    ledger_type],
            ), False
        except Ledger.DoesNotExist:
            last_ledger = Ledger.objects.order_by('number').last()
            last_ledger_number = last_ledger.number if last_ledger else 0
            return Ledger.objects.create(
                name=ledger_type + unicode(entity),
                type=ledger_type,
                entity_content_type=ContentType.objects.get_for_model(entity),
                entity_id=entity.pk,
                increased_by_debits=self.ACCOUNT_TYPE_TO_INCREASED_BY_DEBITS[
                    ledger_type],
                number=last_ledger_number + 1
            ), True

    def get_or_create_ledger_by_name(self, name, increased_by_debits):
        try:
            return Ledger.objects.get(
                type='',
                entity_content_type=None,
                entity_id=None,
                name=name,
                increased_by_debits=increased_by_debits,
            )
        except Ledger.DoesNotExist:
            last_ledger = Ledger.objects.order_by('number').last()
            last_ledger_number = last_ledger.number if last_ledger else 0
            return Ledger.objects.create(
                name=name,
                type='',
                entity_content_type=None,
                entity_id=None,
                increased_by_debits=increased_by_debits,
                number=last_ledger_number + 1
            )


class Ledger(NonDeletableModel, models.Model):
    """
    Ledgers are the record of debits and credits for a given entity.
    """
    class Meta:
        unique_together = ('type', 'entity_content_type', 'entity_id')

    # Fields for object-attached Ledgers
    type = models.CharField(
        help_text=_("The ledger type, eg Accounts Receivable, Revenue, etc"),
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
    name = models.CharField(
        help_text=_("Name of this ledger"),
        unique=True,
        max_length=255)
    number = models.PositiveIntegerField(
        help_text=_("Unique numeric identifier for this ledger"),
        unique=True)
    description = models.TextField(
        help_text=_("Any notes to go along with this Transaction."),
        blank=True)
    increased_by_debits = models.BooleanField(
        help_text="All accounts (and their corresponding ledgers) are of one of two types: either debits increase the value of an account or credits do.  By convention, asset and expense accounts are of the former type, while liabilities, equity, and revenue are of the latter.",  # nopep8
        default=None,
    )

    # Fields for both types of Ledgers

    objects = LedgerManager()

    def get_balance(self):
        """Get the current balance on this Ledger."""
        return self.entries.aggregate(balance=Sum('amount'))['balance']

    def __unicode__(self):
        return self.name or repr(self.entity)


class LedgerEntry(NonDeletableModel, models.Model):
    """A single entry in a single column in a ledger.

    LedgerEntries must always be part of a transaction so that they balance
    according to double-entry bookkeeping.
    """
    class Meta:
        verbose_name_plural = "ledger entries"

    ledger = models.ForeignKey(
        Ledger,
        related_name='entries')
    transaction = models.ForeignKey(
        Transaction,
        related_name='entries')

    entry_id = models.UUIDField(
        help_text=_("UUID for this ledger entry"),
        default=uuid.uuid4)

    amount = models.DecimalField(
        help_text=_(
            NEGATIVE_DEBITS_HELP_TEXT
            if getattr(settings, 'DEBITS_ARE_NEGATIVE', False)
            else POSITIVE_DEBITS_HELP_TEXT
        ),
        max_digits=24,
        decimal_places=4)
    action_type = models.CharField(
        help_text=_("Type of action that created this LedgerEntry"),
        max_length=128,
        blank=True)

    def __unicode__(self):
        return u"LedgerEntry: ${amount} in {ledger}".format(
            amount=self.amount, ledger=self.ledger)


class LedgerBalance(TimeStampedModel):
    """
    Denormalized ledger balances for related objects.
    """
    class Meta:
        unique_together = (
            ('ledger', 'related_object_content_type', 'related_object_id'),
        )

    ledger = models.ForeignKey(
        'Ledger')

    related_object_content_type = models.ForeignKey(
        ContentType)
    related_object_id = models.PositiveIntegerField(
        db_index=True)
    related_object = GenericForeignKey(
        'related_object_content_type',
        'related_object_id')

    balance = models.DecimalField(
        default=Decimal(0),
        max_digits=24,
        decimal_places=4)


def LedgerBalances():
    """
    Make a relation from an evidence model to its LedgerBalance entries.
    """
    return GenericRelation(
        'ledger.LedgerBalance',
        content_type_field='related_object_content_type',
        object_id_field='related_object_id',
    )
