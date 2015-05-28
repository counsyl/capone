from decimal import Decimal as D

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import TestCase

from ledger.api.actions import Charge
from ledger.api.actions import TransactionCtx
from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.tests.factories import UserFactory


class TestLedgerEntryBase(TestCase):
    def setUp(self):
        self.entity = UserFactory()
        self.user = UserFactory()
        self.ledger, _ = Ledger.objects.get_or_create_ledger(
            self.entity,
            Ledger.LEDGER_ACCOUNTS_RECEIVABLE)


class TestLedgerEntry(TestLedgerEntryBase):
    def test_entry_requires_transaction(self):
        self.assertRaises(
            IntegrityError,
            LedgerEntry.objects.create,
            ledger=self.ledger, amount=D(100))

    def test_cant_delete(self):
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Charge(self.entity, D(100)))
        ledger_entries = txn.transaction.entries.all()
        self.assertRaises(PermissionDenied, ledger_entries[0].delete)
