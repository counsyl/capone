"""
These models are used by the `ledger` tests to demonstrate how Orders and
CreditCardTransactions could be handled in your system.
"""
from __future__ import unicode_literals
from decimal import Decimal

from django.db import models

from ledger.models import LedgerBalances


class Order(models.Model):
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
