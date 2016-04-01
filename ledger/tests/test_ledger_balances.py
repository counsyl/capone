from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from ledger.models import LedgerBalance
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import OrderFactory


class TestLedgerBalances(TestCase):

    def setUp(self):
        self.order_1, self.order_2 = OrderFactory.create_batch(2)
        self.ar_ledger = LedgerFactory(name='A/R')
        self.cash_ledger = LedgerFactory(name='Cash')

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

    def test_no_balances(self):
        self.assert_objects_have_ledger_balances(
            (self.order_1, self.ar_ledger, None),
            (self.order_1, self.cash_ledger, None),
            (self.order_2, self.ar_ledger, None),
            (self.order_2, self.cash_ledger, None),
        )
