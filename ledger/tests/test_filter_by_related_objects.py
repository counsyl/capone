from decimal import Decimal as D

from django.test import TestCase

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.models import LedgerEntry
from ledger.models import MatchType
from ledger.models import Transaction
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import UserFactory


class TestFilterByRelatedObjects(TestCase):
    AMOUNT = D('100')

    @classmethod
    def _create_transaction_with_evidence(cls, evidence):
        return create_transaction(
            cls.create_user,
            evidence=evidence,
            ledger_entries=[
                LedgerEntry(
                    ledger=cls.ledger,
                    amount=credit(cls.AMOUNT)),
                LedgerEntry(
                    ledger=cls.ledger,
                    amount=debit(cls.AMOUNT)),
            ]
        )

    @classmethod
    def setUpTestData(cls):
        cls.create_user = UserFactory()

        cls.order_1 = OrderFactory()
        cls.order_2 = OrderFactory()
        cls.order_not_in_transaction = OrderFactory()

        cls.ledger = LedgerFactory()

        cls.transaction_with_both_orders = (
            cls._create_transaction_with_evidence([
                cls.order_1,
                cls.order_2,
            ])
        )
        cls.transaction_with_only_order_1 = (
            cls._create_transaction_with_evidence([
                cls.order_1,
            ])
        )
        cls.transaction_with_only_order_2 = (
            cls._create_transaction_with_evidence([
                cls.order_1,
            ])
        )
        cls.transaction_with_neither_order = (
            cls._create_transaction_with_evidence([
                OrderFactory(),
            ])
        )

    def test_any_filter(self):
        self.assertIn(
            self.transaction_with_both_orders,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ANY)
        )

        self.assertIn(
            self.transaction_with_only_order_1,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ANY)
        )

        self.assertIn(
            self.transaction_with_only_order_2,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ANY)
        )

        self.assertNotIn(
            self.transaction_with_neither_order,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ANY)
        )

    def test_any_filter_no_evidence(self):
        self.assertEqual(
            set(Transaction.objects.all().values_list('id')),
            set(Transaction.objects.filter_by_related_objects(
                [], match_type=MatchType.ANY).values_list('id'))
        )

    def test_all_filter(self):
        self.assertIn(
            self.transaction_with_both_orders,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ALL)
        )

        self.assertNotIn(
            self.transaction_with_only_order_1,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ALL)
        )

        self.assertNotIn(
            self.transaction_with_only_order_2,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ALL)
        )

        self.assertNotIn(
            self.transaction_with_neither_order,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ALL)
        )

        transaction_with_three_orders = (
            self._create_transaction_with_evidence([
                self.order_1,
                self.order_2,
                OrderFactory(),
            ])
        )
        self.assertIn(
            transaction_with_three_orders,
            Transaction.objects.filter_by_related_objects([
                self.order_1, self.order_2,
            ], match_type=MatchType.ALL)
        )

    def test_all_filter_no_evidence(self):
        self.assertEqual(
            set(Transaction.objects.all().values_list('id')),
            set(Transaction.objects.filter_by_related_objects(
                [], match_type=MatchType.ALL).values_list('id'))
        )

    def test_none_filter(self):
        with self.assertRaises(NotImplementedError):
            Transaction.objects.filter_by_related_objects(
                match_type=MatchType.NONE)

    def test_none_filter_no_evidence(self):
        with self.assertRaises(NotImplementedError):
            Transaction.objects.filter_by_related_objects(
                match_type=MatchType.NONE)

    def test_exact_filter(self):
        with self.assertRaises(NotImplementedError):
            Transaction.objects.filter_by_related_objects(
                match_type=MatchType.EXACT)

    def test_exact_filter_no_evidence(self):
        with self.assertRaises(NotImplementedError):
            Transaction.objects.filter_by_related_objects(
                match_type=MatchType.EXACT)

    def test_invalid_match_type(self):
        with self.assertRaises(ValueError):
            Transaction.objects.filter_by_related_objects(match_type='foo')
