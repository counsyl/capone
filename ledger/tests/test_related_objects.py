from decimal import Decimal as D

from django.test import TestCase

from ledger.api.actions import Charge
from ledger.api.actions import TransactionCtx
from ledger.models import Ledger
from ledger.models import Transaction
from ledger.tests.factories import UserFactory


class _TestRelatedObjectBase(TestCase):
    def setUp(self):
        super(_TestRelatedObjectBase, self).setUp()
        self.entity = UserFactory()
        self.user = UserFactory()
        self.ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity,
            Ledger.LEDGER_ACCOUNTS_RECEIVABLE)

        # Record a few charges due to different related objects
        self.related_objects_user_list = [UserFactory() for x in range(3)]
        model = self.related_objects_user_list[0].__class__
        self.related_objects_user_qs = model.objects.filter(
            id__in=[obj.id for obj in self.related_objects_user_list])

        amount = D(100)
        for related_object in self.related_objects_user_list:
            with TransactionCtx(related_object, self.user) as txn:
                txn.record(Charge(self.entity, amount))
        self.charge = txn.transaction

        self.related_objects_different_types = [self.charge] + \
            self.related_objects_user_list
        # Related objects can be anything, so just make it the last used
        # Charge from above
        with TransactionCtx(self.charge, self.user) as txn:
            txn.record(Charge(self.entity, amount))

    def get_queryset(self):
        raise NotImplementedError(
            "You must return a queryset that has a "
            "filter_by_related_objects method")

    def test_no_related_objects(self):
        related_txns = self.get_queryset().filter_by_related_objects()
        self.assertEqual(self.get_queryset().count(),
                         related_txns.count())

    def test_related_object_queryset(self):
        related_txns = self.get_queryset().filter_by_related_objects(
            self.related_objects_user_qs, require_all=False)
        self.assertEqual(len(self.related_objects_user_qs),
                         related_txns.count())

    def test_related_object_empty_queryset(self):
        related_txns = self.get_queryset().filter_by_related_objects(
            self.related_objects_user_qs.none())
        self.assertEqual(0, related_txns.count())

    def test_related_object_list(self):
        related_txns = self.get_queryset().filter_by_related_objects(
            self.related_objects_user_list, require_all=False)
        self.assertEqual(len(self.related_objects_user_list),
                         related_txns.count())

    def test_related_object_empty_list(self):
        related_txns = self.get_queryset().filter_by_related_objects([])
        self.assertEqual(0, related_txns.count())

    def test_related_object_different_types(self):
        related_txns = self.get_queryset().filter_by_related_objects(
            self.related_objects_different_types, require_all=False)
        self.assertEqual(len(self.related_objects_different_types),
                         related_txns.count())

    def test_filter_by_single_related_object(self):
        related_txns = self.get_queryset().filter_by_related_objects(
            self.charge)
        self.assertEqual(1, related_txns.count())


class TestRelatedObjectFilterLedgerEntry(_TestRelatedObjectBase):
    def get_queryset(self):
        return self.ledger.entries


class TestRelatedObjectFilter(_TestRelatedObjectBase):
    def get_queryset(self):
        return Transaction.objects


class TestRelatedObjectAllRequired(TestCase):
    def setUp(self):
        super(TestRelatedObjectAllRequired, self).setUp()
        Transaction.objects.all().delete()
        self.entity = UserFactory()
        self.user = UserFactory()
        self.ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity,
            Ledger.LEDGER_ACCOUNTS_RECEIVABLE)
        self.ro1 = UserFactory(username="ro1")
        self.ro2 = UserFactory(username="ro2")
        self.ro3 = UserFactory(username="ro3")

        with TransactionCtx(
                self.ro1, self.user,
                secondary_related_objects=[self.ro2]) as txn:
            txn.record(Charge(self.entity, D(100)))
        with TransactionCtx(
                self.ro1, self.user,
                secondary_related_objects=[self.ro3]) as txn:
            txn.record(Charge(self.entity, D(100)))

    def test_any(self):
        # When selecting for a single object, require_all has no noticeable
        # effect
        for require_all in [True, False]:
            self.assertEqual(
                Transaction.objects.filter_by_related_objects(
                    self.ro1, require_all=require_all).count(),
                2)
            self.assertEqual(
                Transaction.objects.filter_by_related_objects(
                    self.ro2, require_all=require_all).count(),
                1)
            self.assertEqual(
                Transaction.objects.filter_by_related_objects(
                    self.ro3, require_all=require_all).count(),
                1)

    def test_all(self):
        # Requiring all objects when filtering for multiple related objects
        # ensures that the returned Transactions related_objects contains
        # *all* of the requested related objects.

        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro1, self.ro2, self.ro3],
                require_all=True).count(),
            0, "There should not be a Transaction with all related objects")
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro1, self.ro2, self.ro3],
                require_all=False).count(),
            2, "Each Transaction should have one of these related objects")

        for ro in [self.ro2, self.ro3]:
            self.assertEqual(
                Transaction.objects.filter_by_related_objects(
                    [self.ro1, ro], require_all=True).count(),
                1,
                "Only one Transaction should have these related objects, "
                "(%s & %s)" % (self.ro1, ro))
            self.assertEqual(
                Transaction.objects.filter_by_related_objects(
                    [self.ro1, ro], require_all=False).count(),
                2, "All Transactions have ro1, so all should be returned")

        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro2, self.ro3], require_all=True).count(),
            0, "No Transactions should have both ro2 and ro3")
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro2, self.ro3], require_all=False).count(),
            2, "Every Transaction should have either ro2 or ro3")

    def test_similar(self):
        # Similar sets of related objects should be ok
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro1, self.ro2], require_all=True).count(),
            1,
        )
        # Create a similar transaction as in setUp
        with TransactionCtx(
                self.ro1, self.user,
                secondary_related_objects=[self.ro2]) as txn:
            txn.record(Charge(self.entity, D(100)))
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro1, self.ro2], require_all=True).count(),
            2,
        )

    def test_mixed_content_types(self):
        with TransactionCtx(
                self.ro1, self.user,
                secondary_related_objects=[self.ro2, self.ledger]) as txn:
            txn.record(Charge(self.entity, D(100)))
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro1, self.ro2], require_all=True).count(),
            2,
        )
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro1, self.ledger], require_all=True).count(),
            1,
        )
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ro1, self.ledger], require_all=False).count(),
            3,
        )
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ledger], require_all=True).count(),
            1,
        )
        self.assertEqual(
            Transaction.objects.filter_by_related_objects(
                [self.ledger], require_all=False).count(),
            1,
        )
