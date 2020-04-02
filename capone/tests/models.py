"""
These models are used by the `capone` tests to demonstrate how Orders and
CreditCardTransactions could be handled in your system.
"""
from decimal import Decimal

from django.db import models

from capone.models import LedgerBalances


class Order(models.Model):
    """
    A fake order used for testing `capone's` evidence functionality.

    This model represents an order of goods and services that would be
    tracked by the organization using `capone`.
    """
    patient_name = models.CharField(
        max_length=255,
    )
    datetime = models.DateTimeField(
        auto_now_add=True,
    )
    amount = models.DecimalField(
        max_digits=24,
        decimal_places=4,
        default=Decimal(0),
    )
    barcode = models.CharField(
        max_length=255,
        unique=True,
    )

    ledger_balances = LedgerBalances()


class CreditCardTransaction(models.Model):
    """
    A fake credit card payment for testing `capone's` evidence functionality.

    This model represents a transaction representing money coming in or going
    out of the organization using `capone`.
    """
    cardholder_name = models.CharField(
        max_length=255,
    )
    datetime = models.DateTimeField(
        auto_now_add=True,
    )
    amount = models.DecimalField(
        max_digits=24,
        decimal_places=4,
        default=Decimal(0),
    )
