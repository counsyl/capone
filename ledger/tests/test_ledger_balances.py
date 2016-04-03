from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.actions import void_transaction
from ledger.models import LedgerBalance
from ledger.models import LedgerEntry
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import UserFactory


class TestLedgerBalances(TestCase):

    def setUp(self):
        self.order_1, self.order_2 = OrderFactory.create_batch(2)
        self.ar_ledger = LedgerFactory(name='A/R')
        self.cash_ledger = LedgerFactory(name='Cash')
        self.user = UserFactory()

    def assert_objects_have_ledger_balances(self, *object_ledger_balances):
        for obj, ledger, balance in object_ledger_balances:
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

    def add_transaction(self, orders, amount):
        return create_transaction(
            self.user,
            evidence=orders,
            ledger_entries=[
                LedgerEntry(
                    ledger=self.ar_ledger,
                    amount=credit(amount)),
                LedgerEntry(
                    ledger=self.cash_ledger,
                    amount=debit(amount)),
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
        amount = Decimal('50.00')

        self.add_transaction([self.order_1], amount)
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(amount)),
            (self.order_1, self.cash_ledger, debit(amount)),
            (self.order_2, self.ar_ledger, None),
            (self.order_2, self.cash_ledger, None),
        )

        self.add_transaction([self.order_2], amount)
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(amount)),
            (self.order_1, self.cash_ledger, debit(amount)),
            (self.order_2, self.ar_ledger, credit(amount)),
            (self.order_2, self.cash_ledger, debit(amount)),
        )

        self.add_transaction([self.order_1], amount)
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(amount) * 2),
            (self.order_1, self.cash_ledger, debit(amount) * 2),
            (self.order_2, self.ar_ledger, credit(amount)),
            (self.order_2, self.cash_ledger, debit(amount)),
        )

        transaction = self.add_transaction(
            [self.order_1, self.order_2], amount)
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(amount) * 3),
            (self.order_1, self.cash_ledger, debit(amount) * 3),
            (self.order_2, self.ar_ledger, credit(amount) * 2),
            (self.order_2, self.cash_ledger, debit(amount) * 2),
        )

        void_transaction(transaction, self.user)
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, credit(amount) * 2),
            (self.order_1, self.cash_ledger, debit(amount) * 2),
            (self.order_2, self.ar_ledger, credit(amount)),
            (self.order_2, self.cash_ledger, debit(amount)),
        )
