from collections import defaultdict
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.test import TransactionTestCase

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.actions import void_transaction
from ledger.models import Ledger
from ledger.models import LedgerBalance
from ledger.models import LedgerEntry
from ledger.models import Transaction
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import UserFactory
from ledger.tests.models import Order
from ledger.utils import rebuild_ledger_balances


class TestLedgerBalances(TransactionTestCase):

    amount = Decimal('50.00')

    def setUp(self):
        self.order_1, self.order_2 = OrderFactory.create_batch(2)
        self.ar_ledger = LedgerFactory(name='A/R')
        self.cash_ledger = LedgerFactory(name='Cash')
        self.user = UserFactory()

    def tearDown(self):
        Transaction.objects.all().delete(really_delete=True)
        (
            Ledger.objects
            .filter(id__in=(self.ar_ledger.id, self.cash_ledger.id))
            .delete(really_delete=True)
        )
        self.order_1.delete()
        self.order_2.delete()
        self.user.delete()

    def assert_objects_have_ledger_balances(self, *object_ledger_balances):
        obj_to_ledger_balances = defaultdict(set)

        for obj, ledger, balance in object_ledger_balances:
            if balance is not None:
                obj_to_ledger_balances[obj].add((ledger.id, balance))
            content_type = ContentType.objects.get_for_model(obj)
            matching_queryset = (
                LedgerBalance
                .objects
                .filter(
                    ledger=ledger,
                    related_object_content_type=content_type,
                    related_object_id=obj.id)
            )

            if balance is None:
                self.assertFalse(matching_queryset.exists())
            else:
                self.assertEqual(matching_queryset.get().balance, balance)

        for obj, ledger_balances in obj_to_ledger_balances.viewitems():
            self.assertEqual(
                set(obj.ledger_balances.values_list('ledger', 'balance')),
                ledger_balances)

    def add_transaction(self, orders):
        return create_transaction(
            self.user,
            evidence=orders,
            ledger_entries=[
                LedgerEntry(
                    ledger=self.ar_ledger,
                    amount=credit(self.amount)),
                LedgerEntry(
                    ledger=self.cash_ledger,
                    amount=debit(self.amount)),
            ],
        )

    def test_no_balances(self):
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, None),
            (self.order_1, self.cash_ledger, None),
            (self.order_2, self.ar_ledger, None),
            (self.order_2, self.cash_ledger, None),
        )

    def test_ledger_balance_update(self):
        self.add_transaction([self.order_1])
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount)),
            (self.order_1, self.cash_ledger, debit(self.amount)),
            (self.order_2, self.ar_ledger, None),
            (self.order_2, self.cash_ledger, None),
        )

        self.add_transaction([self.order_2])
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount)),
            (self.order_1, self.cash_ledger, debit(self.amount)),
            (self.order_2, self.ar_ledger, credit(self.amount)),
            (self.order_2, self.cash_ledger, debit(self.amount)),
        )

        self.add_transaction([self.order_1])
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount) * 2),
            (self.order_1, self.cash_ledger, debit(self.amount) * 2),
            (self.order_2, self.ar_ledger, credit(self.amount)),
            (self.order_2, self.cash_ledger, debit(self.amount)),
        )

        transaction = self.add_transaction([self.order_1, self.order_2])
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount) * 3),
            (self.order_1, self.cash_ledger, debit(self.amount) * 3),
            (self.order_2, self.ar_ledger, credit(self.amount) * 2),
            (self.order_2, self.cash_ledger, debit(self.amount) * 2),
        )

        void_transaction(transaction, self.user)
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount) * 2),
            (self.order_1, self.cash_ledger, debit(self.amount) * 2),
            (self.order_2, self.ar_ledger, credit(self.amount)),
            (self.order_2, self.cash_ledger, debit(self.amount)),
        )

    def test_rebuild_ledger_balance(self):
        rebuild_ledger_balances()
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, None),
            (self.order_1, self.cash_ledger, None),
            (self.order_2, self.ar_ledger, None),
            (self.order_2, self.cash_ledger, None),
        )

        self.add_transaction([self.order_1])
        rebuild_ledger_balances()
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount)),
            (self.order_1, self.cash_ledger, debit(self.amount)),
            (self.order_2, self.ar_ledger, None),
            (self.order_2, self.cash_ledger, None),
        )

        self.add_transaction([self.order_2])
        rebuild_ledger_balances()
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount)),
            (self.order_1, self.cash_ledger, debit(self.amount)),
            (self.order_2, self.ar_ledger, credit(self.amount)),
            (self.order_2, self.cash_ledger, debit(self.amount)),
        )

        self.add_transaction([self.order_1])
        rebuild_ledger_balances()
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount) * 2),
            (self.order_1, self.cash_ledger, debit(self.amount) * 2),
            (self.order_2, self.ar_ledger, credit(self.amount)),
            (self.order_2, self.cash_ledger, debit(self.amount)),
        )

        transaction = self.add_transaction([self.order_1, self.order_2])
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount) * 3),
            (self.order_1, self.cash_ledger, debit(self.amount) * 3),
            (self.order_2, self.ar_ledger, credit(self.amount) * 2),
            (self.order_2, self.cash_ledger, debit(self.amount) * 2),
        )

        void_transaction(transaction, self.user)
        rebuild_ledger_balances()
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount) * 2),
            (self.order_1, self.cash_ledger, debit(self.amount) * 2),
            (self.order_2, self.ar_ledger, credit(self.amount)),
            (self.order_2, self.cash_ledger, debit(self.amount)),
        )

        LedgerBalance.objects.update(balance=Decimal('1.00'))
        LedgerBalance.objects.first().delete()
        rebuild_ledger_balances()
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(self.amount) * 2),
            (self.order_1, self.cash_ledger, debit(self.amount) * 2),
            (self.order_2, self.ar_ledger, credit(self.amount)),
            (self.order_2, self.cash_ledger, debit(self.amount)),
        )

    def test_ledger_balances_filtering(self):
        Order.objects.update(amount=self.amount * 2)

        def all_cash_orders():
            return set(
                Order.objects
                .filter(
                    id__in=(self.order_1.id, self.order_2.id),
                    ledger_balances__ledger=self.cash_ledger,
                    ledger_balances__balance=F('amount'),
                )
            )

        self.assertEqual(all_cash_orders(), set())

        self.add_transaction([self.order_1])
        self.assertEqual(all_cash_orders(), set())

        self.add_transaction([self.order_1])
        self.assertEqual(all_cash_orders(), {self.order_1})

        self.add_transaction([self.order_2])
        self.assertEqual(all_cash_orders(), {self.order_1})

        self.add_transaction([self.order_2])
        self.assertEqual(all_cash_orders(), {self.order_1, self.order_2})
