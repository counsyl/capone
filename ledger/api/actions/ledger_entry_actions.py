"""Ledger actions are common operations that you'll probably want to perform.
"""
import itertools

from django.db.transaction import atomic

from ledger.models import Ledger
from ledger.models import LEDGER_ACCOUNTS_RECEIVABLE
from ledger.models import LEDGER_CASH
from ledger.models import LEDGER_REVENUE
from ledger.models import LedgerEntry


class LedgerEntryAction(object):
    """A LedgerEntryAction is a common LedgerEntry-based operation."""
    def __init__(self, amount):
        super(LedgerEntryAction, self).__init__()
        if self.validate_amount(amount):
            self.amount = amount

    @classmethod
    def validate_amount(cls, amount):
        """Validate the dollar amount for this action.

        Returns the validated amount or raises a ValueError.
        """
        if amount < 0:
            raise ValueError("Amounts must be non-negative")
        return True

    @atomic
    def get_ledger_entries(self):
        """Record debits and credits against an entity.

        Args:
            amount: The amount to charge the entity.
        """
        # Remember! Debits are positive, credits are negative!
        credit = LedgerEntry(
            ledger=self._get_credit_ledger(),
            amount=-self.amount,
            action_type=type(self).__name__)
        debit = LedgerEntry(
            ledger=self._get_debit_ledger(),
            amount=self.amount,
            action_type=type(self).__name__)
        return [credit, debit]

    def _get_credit_ledger(self):
        """Get the Ledger you want to use for credits.

        Returns a Ledger.
        """
        raise NotImplementedError("You must implement _get_credit_ledger")

    def _get_debit_ledger(self):
        """Get the Ledger you want to use for debits.

        Returns a Ledger.
        """
        raise NotImplementedError("You must implement _get_debit_ledger")


class SingleEntityLedgerEntryAction(LedgerEntryAction):
    def __init__(self, entity, amount):
        super(SingleEntityLedgerEntryAction, self).__init__(amount=amount)
        self.entity = entity

    def __repr__(self):
        return "<%s: %s %s>" % (type(self).__name__,
                                self.amount,
                                repr(self.entity))


class Charge(SingleEntityLedgerEntryAction):
    """Charge an entity a given amount."""
    def _get_credit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_REVENUE)
        return ledger

    def _get_debit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        return ledger


class Payment(SingleEntityLedgerEntryAction):
    """Record a payment from an entity."""
    def _get_credit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        return ledger

    def _get_debit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_CASH)
        return ledger


class Refund(SingleEntityLedgerEntryAction):
    """Record a payment to an entity (a refund)."""
    def _get_credit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_CASH)
        return ledger

    def _get_debit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        return ledger


class WriteDown(SingleEntityLedgerEntryAction):
    """Write down an amount.

    TODO: Should WriteDown allow us to go negative?
    """
    def _get_credit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_ACCOUNTS_RECEIVABLE)
        return ledger

    def _get_debit_ledger(self):
        ledger, created = Ledger.objects.get_or_create_ledger(
            self.entity, LEDGER_REVENUE)
        return ledger


class TransferAmount(LedgerEntryAction):
    """Transfer an amount from one entity's ledger to another."""
    def __init__(self, entity_from, entity_to, amount):
        super(TransferAmount, self).__init__(amount=amount)
        self.entity_from = entity_from
        self.entity_to = entity_to

    def __repr__(self):
        return "<%s: %s from %s to %s>" % (type(self).__name__,
                                           self.amount,
                                           repr(self.entity_from),
                                           repr(self.entity_to))

    @atomic
    def get_ledger_entries(self):
        entries = []
        for entry in itertools.chain(
                WriteDown(self.entity_from, self.amount).get_ledger_entries(),
                Charge(self.entity_to, self.amount).get_ledger_entries()):
            entry.action_type = type(self).__name__
            entries.append(entry)
        return entries
