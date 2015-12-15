from decimal import Decimal as D

from django.test import TestCase

from ledger.models import Ledger
from ledger.models import LedgerEntry
from ledger.api.actions import TransactionContext
from ledger.tests.factories import CreditCardTransactionFactory
from ledger.tests.factories import OrderFactory
from ledger.tests.factories import UserFactory


class TestCompanyWideLedgers(TestCase):
    def test_using_company_wide_ledgers_for_reconciliation(self):
        user = UserFactory()
        order = OrderFactory()
        credit_card_transaction = CreditCardTransactionFactory()

        # create four company-wide ledgers: "Stripe Cash (unreconciled)",
        # "Stripe Cash (reconciled)", "A/R", and "Revenue"
        accounts_receivable = Ledger.objects.get_or_create_ledger_by_name(
            'Accounts Receivable',
            are_debits_positive=True,
        )
        stripe_unrecon = Ledger.objects.get_or_create_ledger_by_name(
            'Stripe Cash (unreconciled)',
            are_debits_positive=True,
        )
        stripe_recon = Ledger.objects.get_or_create_ledger_by_name(
            'Stripe Cash (reconciled)',
            are_debits_positive=True,
        )
        revenue = Ledger.objects.get_or_create_ledger_by_name(
            'Revenue',
            are_debits_positive=False,
        )

        # add an entry debiting AR and crediting Revenue: this entry should
        # reference the Order
        with TransactionContext(order, user) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(revenue, D(100)),
                LedgerEntry(accounts_receivable, D(-100)),
            ])

        # add an entry crediting AR and debiting Stripe/un: this entry should
        # reference the PGXX
        with TransactionContext(
                credit_card_transaction, user) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(accounts_receivable, D(100)),
                LedgerEntry(stripe_unrecon, D(-100))
            ])

        # add an entry crediting Stripe/un and debiting Stripe/recon: this
        # entry should reference both an Order and a PGXX
        with TransactionContext(
                order,
                user,
                secondary_related_objects=[credit_card_transaction]
        ) as txn_recognize:
            txn_recognize.record_entries([
                LedgerEntry(stripe_unrecon, D(100)),
                LedgerEntry(stripe_recon, D(-100))
            ])
