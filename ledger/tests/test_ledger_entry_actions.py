import mock
from decimal import Decimal as D

from django.test import TestCase

from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.models import Ledger
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LEDGER_CASH
from ledger.models import LEDGER_REVENUE
from ledger.tests.factories import UserFactory


class LedgerEntryActionSetUp(TestCase):
    def setUp(self):
        super(LedgerEntryActionSetUp, self).setUp()
        self.entity_1 = UserFactory()
        self.entity_2 = UserFactory()
        self.creation_user = UserFactory()
        self.entity_1_ar_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_1, LEDGER_ACCOUNTS_RECEIVABLE)
        self.entity_1_rev_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_1, LEDGER_REVENUE)
        self.entity_1_cash_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_1, LEDGER_CASH)
        self.entity_2_ar_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_2, LEDGER_ACCOUNTS_RECEIVABLE)
        self.entity_2_rev_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_2, LEDGER_REVENUE)
        self.entity_2_cash_ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity_2, LEDGER_CASH)


class TestCreditAndDebit(TestCase):
    """
    Test that `credit` and `debit` return the correctly signed amounts.
    """
    AMOUNT = D(100)

    def assertPositive(self, amount):
        self.assertGreaterEqual(amount, 0)

    def assertNegative(self, amount):
        self.assertLess(amount, 0)

    def test_credit_and_debit_helper_functions(self):
        with mock.patch('ledger.api.actions.settings') as mock_settings:
            mock_settings.DEBITS_ARE_NEGATIVE = True
            self.assertPositive(credit(self.AMOUNT))
            self.assertNegative(debit(self.AMOUNT))
        with mock.patch('ledger.api.actions.settings') as mock_settings:
            mock_settings.DEBITS_ARE_NEGATIVE = False
            self.assertNegative(credit(self.AMOUNT))
            self.assertPositive(debit(self.AMOUNT))

    def test_validation_error(self):
        self.assertRaises(ValueError, credit, -self.AMOUNT)
        self.assertRaises(ValueError, debit, -self.AMOUNT)
