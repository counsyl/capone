from __future__ import unicode_literals
from decimal import Decimal as D

from django.test import TestCase
from nose_parameterized import parameterized

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

        cls.transaction_with_three_orders = (
            cls._create_transaction_with_evidence([
                cls.order_1,
                cls.order_2,
                OrderFactory(),
            ])
        )

    @parameterized.expand([
        (MatchType.ANY, Transaction.objects.all().values_list('id')),
        (MatchType.ALL, Transaction.objects.all().values_list('id')),
        (MatchType.NONE, Transaction.objects.all().values_list('id')),
        (MatchType.EXACT, Transaction.objects.none().values_list('id')),
    ])
    def test_filter_with_no_evidence(self, match_type, result_queryset):
        self.assertEqual(
            set(result_queryset),
            set(Transaction.objects.filter_by_related_objects(
                [], match_type=match_type).values_list('id'))
        )

    @parameterized.expand([
        (MatchType.ANY, [True, True, True, False, True]),
        (MatchType.ALL, [True, False, False, False, True]),
        (MatchType.NONE, [False, False, False, True, False]),
        (MatchType.EXACT, [True, False, False, False, False]),
    ])
    def test_filters(self, match_type, results):
        query_list = [
            self.transaction_with_both_orders,
            self.transaction_with_only_order_1,
            self.transaction_with_only_order_2,
            self.transaction_with_neither_order,
            self.transaction_with_three_orders,
        ]

        for query, query_should_be_in_result in zip(query_list, results):
            if query_should_be_in_result:
                self.assertIn(
                    query,
                    Transaction.objects.filter_by_related_objects(
                        [self.order_1, self.order_2],
                        match_type=match_type
                    )
                )
            else:
                self.assertNotIn(
                    query,
                    Transaction.objects.filter_by_related_objects([
                        self.order_1, self.order_2,
                    ], match_type=match_type)
                )

    @parameterized.expand([
        (MatchType.ANY, 1),
        (MatchType.ALL, 1),
        (MatchType.NONE, 1),
        (MatchType.EXACT, 4),
    ])
    def test_query_counts(self, match_type, query_counts):
        with self.assertNumQueries(query_counts):
            list(Transaction.objects.filter_by_related_objects(
                [self.order_1],
                match_type=match_type
            ))

        with self.assertNumQueries(query_counts):
            list(Transaction.objects.filter_by_related_objects(
                [self.order_1, self.order_2],
                match_type=match_type
            ))

    def test_invalid_match_type(self):
        with self.assertRaises(ValueError):
            Transaction.objects.filter_by_related_objects(match_type='foo')

    def test_chaining_filter_to_existing_queryset(self):
        self.assertEquals(Transaction.objects.count(), 5)

        self.assertEquals(
            Transaction.objects.filter_by_related_objects(
                [self.order_1]).count(), 4)

        transactions_restricted_by_ledger = (
            Transaction.objects.filter(ledgers__in=[self.ledger])
        )

        self.assertEquals(
            transactions_restricted_by_ledger.filter_by_related_objects(
                [self.order_1]).distinct().count(), 4)
