from datetime import datetime
from decimal import Decimal as D

from django.test import TestCase

from ledger.api.actions import Charge
from ledger.api.actions import Payment
from ledger.api.actions import Refund
from ledger.api.actions import TransactionCtx
from ledger.api.actions import TransferAmount
from ledger.api.actions import VoidTransaction
from ledger.api.actions import WriteDown
from ledger.api.invoice import Invoice
from ledger.models import Ledger
from ledger.models import Transaction
from ledger.tests.factories import UserFactory


class TestInvoicingBase(TestCase):
    def setUp(self):
        self.user = UserFactory()
        # The Entity can be anything, so just make it a User
        self.entity_1 = UserFactory()
        self.entity_2 = UserFactory()


class TestSimpleInvoices(TestInvoicingBase):
    def test_simple_invoice(self):
        """Entity owes us money."""
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Charge(self.entity_1, D(100)))
        invoice = Invoice(self.entity_1)
        self.assertEqual(invoice.amount, D(100))
        self.assertEqual(invoice.ledger.entity, self.entity_1)

    def test_simple_refund_invoice(self):
        """Entity has paid too much and needs a refund."""
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Charge(self.entity_1, D(100)))
        # Entity_1 overpays by $100!
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Payment(self.entity_1, D(200)))
        invoice = Invoice(self.entity_1)
        # ...so we owe entity_1 $100
        self.assertEqual(invoice.amount, D(-100))
        self.assertEqual(invoice.ledger.entity, self.entity_1)

    def test_simple_write_down(self):
        """Entity negotiated a reduced rate, so we are comping some amount."""
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Charge(self.entity_1, D(1000)))
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(WriteDown(self.entity_1, D(501)))
        invoice = Invoice(self.entity_1)
        self.assertEqual(invoice.amount, D(499))


class TestInvoiceReversals(TestInvoicingBase):
    """Reversed transactions shouldn't screw up invoices."""
    def setUp(self):
        super(TestInvoiceReversals, self).setUp()
        self.charge_amount = D(1000)
        self.transfer_amount = D(200)
        self.comp_amount_1 = D(90)
        self.comp_amount_2 = D(10)

        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Charge(self.entity_1, self.charge_amount))

        with TransactionCtx(self.user, self.user) as txn:
            txn.record(TransferAmount(self.entity_1, self.entity_2,
                                      self.transfer_amount))
            txn.record(WriteDown(self.entity_2, self.comp_amount_1))
        self.transfer_txn = txn.transaction

        with TransactionCtx(self.user, self.user) as txn:
            txn.record(WriteDown(self.entity_2, self.comp_amount_2))
        self.comp_txn = txn.transaction

    def _assert_invoices(self, entity_1_amount, entity_2_amount):
        entity_1_invoice = Invoice(self.entity_1)
        entity_2_invoice = Invoice(self.entity_2)
        self.assertEqual(entity_1_invoice.amount, entity_1_amount)
        self.assertEqual(entity_2_invoice.amount, entity_2_amount)

    def test_amounts(self):
        self._assert_invoices(
            self.charge_amount - self.transfer_amount,
            self.transfer_amount - self.comp_amount_1 - self.comp_amount_2)

    def test_void_amounts(self):
        """Make sure that voiding a transaction adds the value back."""
        VoidTransaction(self.comp_txn, self.user).record()

        self._assert_invoices(
            self.charge_amount - self.transfer_amount,
            self.transfer_amount - self.comp_amount_1)

        VoidTransaction(self.transfer_txn, self.user).record()
        self._assert_invoices(self.charge_amount, 0)

    def test_voids_can_appear_or_be_hidden_on_invoice_transaction_list(self):
        # Contains a Charge and a Transfer
        invoice_1 = Invoice(self.entity_1)
        for exclude_voids in [True, False]:
            self.assertEqual(
                len(invoice_1.get_ledger_entries(exclude_voids)), 2)

        # Contains a Transfer and two WriteDowns
        invoice_2 = Invoice(self.entity_2)
        for exclude_voids in [True, False]:
            self.assertEqual(
                len(invoice_2.get_ledger_entries(exclude_voids)), 3)

        # Void the WriteDown
        VoidTransaction(self.comp_txn, self.user).record()

        # Invoice_1 should be unchanged
        invoice_1 = Invoice(self.entity_1)
        for exclude_voids in [True, False]:
            self.assertEqual(
                len(invoice_1.get_ledger_entries(exclude_voids)), 2)

        # But invoice_2 should be different
        invoice_2 = Invoice(self.entity_2)
        self.assertEqual(
            len(invoice_2.get_ledger_entries(exclude_voids=True)), 2)
        self.assertEqual(
            len(invoice_2.get_ledger_entries(exclude_voids=False)), 4)
        comp_entry = self.comp_txn.entries.get(ledger=invoice_2.ledger)
        self.assertNotIn(
            comp_entry, invoice_2.get_ledger_entries(exclude_voids=True))
        self.assertIn(
            comp_entry, invoice_2.get_ledger_entries(exclude_voids=False))

    def test_multi_entry_voids_can_appear_or_be_hidden(self):
        # Contains a Charge and a Transfer
        invoice_1 = Invoice(self.entity_1)
        for exclude_voids in [True, False]:
            self.assertEqual(
                len(invoice_1.get_ledger_entries(exclude_voids)), 2)

        # Contains a Transfer and two WriteDowns
        invoice_2 = Invoice(self.entity_2)
        for exclude_voids in [True, False]:
            self.assertEqual(
                len(invoice_2.get_ledger_entries(exclude_voids)), 3)

        # Void the Transfer/WriteDown combo
        VoidTransaction(self.transfer_txn, self.user).record()

        # Invoice_1 should be altered
        invoice_1 = Invoice(self.entity_1)
        self.assertEqual(len(invoice_1.get_ledger_entries(True)), 1)
        self.assertEqual(len(invoice_1.get_ledger_entries(False)), 3)

        # Invoice_2 should be altered as well
        invoice_2 = Invoice(self.entity_2)
        self.assertEqual(
            len(invoice_2.get_ledger_entries(exclude_voids=True)), 1)
        self.assertEqual(
            len(invoice_2.get_ledger_entries(exclude_voids=False)), 5)
        transfer_and_comp_entries = self.transfer_txn.entries.filter(
            ledger=invoice_2.ledger)
        for entry in transfer_and_comp_entries:
            self.assertNotIn(
                entry, invoice_2.get_ledger_entries(exclude_voids=True))
            self.assertIn(
                entry, invoice_2.get_ledger_entries(exclude_voids=False))

    def test_void_void_hidden(self):
        # Void the comp first
        invoice = Invoice(self.entity_2)
        self.assertEqual(len(invoice.get_ledger_entries()), 3)

        void_comp_txn = VoidTransaction(self.comp_txn, self.user).record()
        invoice = Invoice(self.entity_2)
        self.assertEqual(len(invoice.get_ledger_entries(True)), 2)
        self.assertEqual(len(invoice.get_ledger_entries(False)), 4)

        # Now void the voided comp, effectively restoring the comp
        void_void_comp_txn = VoidTransaction(void_comp_txn, self.user).record()
        invoice = Invoice(self.entity_2)
        self.assertEqual(len(invoice.get_ledger_entries(True)), 3)
        self.assertEqual(len(invoice.get_ledger_entries(False)), 5)

        # And if we void the void void, it should re-void the comp
        VoidTransaction(void_void_comp_txn, self.user).record()
        invoice = Invoice(self.entity_2)
        self.assertEqual(len(invoice.get_ledger_entries(True)), 2)
        self.assertEqual(len(invoice.get_ledger_entries(False)), 6)

    def test_voids_and_payments(self):
        # Get the amount entity_2 owes
        invoice = Invoice(self.entity_2)
        payment_amount = invoice.amount

        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Payment(self.entity_2, payment_amount))

        self._assert_invoices(self.charge_amount - self.transfer_amount, 0)

        # Voiding the comp and transfer transactions should mean we now
        # *owe* entity_2
        void_comp = VoidTransaction(self.comp_txn, self.user).record()
        void_transfer = VoidTransaction(self.transfer_txn, self.user).record()

        self._assert_invoices(self.charge_amount, -payment_amount)

        # And let's void those voids
        VoidTransaction(void_transfer, self.user).record()
        self._assert_invoices(self.charge_amount - self.transfer_amount,
                              self.comp_amount_2)
        VoidTransaction(void_comp, self.user).record()
        # And entity_2's responsibility is back to 0!
        self._assert_invoices(self.charge_amount - self.transfer_amount, 0)

    def test_wrong_void_syntax(self):
        with TransactionCtx(self.user, self.user) as txn:
            self.assertRaises(Transaction.UnvoidableTransactionException,
                              txn.record,
                              VoidTransaction(self.transfer_txn, self.user))


class TestInvoiceRefunds(TestInvoicingBase):
    def setUp(self):
        super(TestInvoiceRefunds, self).setUp()
        self.charge_amount = D(1000)
        self.payment_amount = D(1500)

        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Charge(self.entity_1, self.charge_amount))
        self.charge = txn.transaction
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Payment(self.entity_1, self.payment_amount))
        self.payment = txn.transaction

    def test_invoice_show_balance(self):
        invoice = Invoice(self.entity_1)
        self.assertTrue(invoice.amount < 0)
        self.assertEqual(invoice.amount,
                         self.charge_amount - self.payment_amount)
        self.assertEqual(len(invoice.get_ledger_entries()), 2)

    def test_invoice_show_refund(self):
        invoice_1 = Invoice(self.entity_1)
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Refund(self.entity_1, -invoice_1.amount))
        refund = txn.transaction
        invoice_2 = Invoice(self.entity_1)
        self.assertNotEqual(invoice_1, invoice_2)
        self.assertIn(refund.entries.get(ledger=invoice_1.ledger),
                      invoice_2.get_ledger_entries())
        self.assertIn(refund.entries.get(ledger=invoice_1.ledger),
                      invoice_2.get_ledger_entries(False))

    def test_refund_from_void(self):
        invoice_1 = Invoice(self.entity_1)
        self.assertEqual(invoice_1.amount,
                         self.charge_amount - self.payment_amount)
        # Voiding the charge results in a bigger refund being owed
        VoidTransaction(self.charge, self.user).record()
        invoice_2 = Invoice(self.entity_1)
        self.assertEqual(invoice_2.amount, -self.payment_amount)
        # If we process the refund, everything should be back to 0
        with TransactionCtx(self.user, self.user) as txn:
            txn.record(Refund(self.entity_1, -invoice_2.amount))
        invoice_3 = Invoice(self.entity_1)
        self.assertEqual(invoice_3.amount, D(0))
        ar_ledger = Ledger.objects.get_ledger(
            self.entity_1, Ledger.LEDGER_ACCOUNTS_RECEIVABLE)
        rev_ledger = Ledger.objects.get_ledger(
            self.entity_1, Ledger.LEDGER_REVENUE)
        cash_ledger = Ledger.objects.get_ledger(
            self.entity_1, Ledger.LEDGER_CASH)
        self.assertEqual(ar_ledger.get_balance(), D(0))
        self.assertEqual(rev_ledger.get_balance(), D(0))
        self.assertEqual(cash_ledger.get_balance(), D(0))


class TestInvoiceBackdatedTransactions(TestInvoicingBase):
    """Invoices may be generated with and without backdated transactions.

    This situation is as follows:
    2013-10-07: Record Charge
    2013-10-08: File to Insurance
    2014-01-08: Decide Insurance isn't going to pay, so transfer charge and
                write it down charge
    2014-01-09: Generate Invoice #1 and send to customer
    2014-01-10: Insurance payment was delayed;
                payment was backdated to 2013-10-10
    2014-01-11: Patient visits website looking to pay invoice #1
                The invoice generated today is different from what they saw
                due to the insurance payment. We can regenerate invoice #1
                given the original invoice's generation date (because it
                will use creation_timestamp instead of posted_timestamp as
                a filter), and we can also generate a new, correct invoice.
    """
    def setUp(self):
        super(TestInvoiceBackdatedTransactions, self).setUp()
        self.user = UserFactory()

        self.order_date = datetime(2013, 10, 7)
        self.file_date = datetime(2013, 10, 8)
        self.write_down_date = datetime(2014, 1, 8)
        self.invoice_1_date = datetime(2014, 1, 9)
        self.date_of_backdated_payment = datetime(2014, 1, 10)
        self.backdated_payment_post_date = datetime(2013, 10, 10)
        self.invoice_2_date = datetime(2014, 1, 11)

        self.charge_amount = D(1000)
        self.customer_responsibility = D(100)

        with TransactionCtx(
                self.user, self.user,
                posted_timestamp=self.order_date) as txn:
            txn.record(Charge(self.entity_1, self.charge_amount))
        self.charge_txn = txn.transaction

        with TransactionCtx(
                self.user, self.user,
                posted_timestamp=self.write_down_date) as txn:
            txn.record(
                TransferAmount(self.entity_1, self.user, self.charge_amount))
            txn.record(
                WriteDown(self.user,
                          self.charge_amount - self.customer_responsibility))
        self.transfer_txn = txn.transaction

        self.user_invoice_1 = Invoice(self.user, timestamp=self.invoice_1_date)
        self.entity_invoice_1 = Invoice(
            self.entity_1, timestamp=self.invoice_1_date)

        with TransactionCtx(
                self.user, self.user,
                posted_timestamp=self.date_of_backdated_payment)\
                as txn:
            txn.record(Payment(self.entity_1, self.charge_amount))
        self.payment_txn = txn.transaction

        # Void the write_down and the transfer
        VoidTransaction(
            self.transfer_txn, self.user,
            posted_timestamp=self.transfer_txn.posted_timestamp).record()

        self.user_invoice_2 = Invoice(self.user, timestamp=self.invoice_2_date)
        self.entity_invoice_2 = Invoice(
            self.entity_1, timestamp=self.invoice_2_date)

    def test_user_invoice_1_entries(self):
        # user_invoice_1 should show the non-voided transfer and write down
        # txns, but not the voids because they hadn't happened yet
        transfer_and_comp_entries = self.transfer_txn.entries.filter(
            ledger=self.user_invoice_1.ledger)
        self.assertEqual(transfer_and_comp_entries.count(), 2)
        for entry in transfer_and_comp_entries.all():
            self.assertIn(entry, self.user_invoice_1.get_ledger_entries(True))

    def test_entity_invoice_1_entries(self):
        # entity_invoice_1 should have the charge and transfer entries
        charge_entry = self.charge_txn.entries.get(
            ledger=self.entity_invoice_1.ledger)
        transfer_entry = self.transfer_txn.entries.get(
            ledger=self.entity_invoice_1.ledger)
        self.assertIn(charge_entry,
                      self.entity_invoice_1.get_ledger_entries(True))
        self.assertIn(transfer_entry,
                      self.entity_invoice_1.get_ledger_entries(True))

    def test_user_invoice_2_entries(self):
        # user_invoice_2 should have no entries
        self.assertEqual(
            [], list(self.user_invoice_2.get_ledger_entries(True)))
        # But if you *want* to see them, they're there
        self.assertEqual(4, len(self.user_invoice_2.get_ledger_entries(False)))

    def test_entity_invoice_2_entries(self):
        # entity_invoice_2 should have:
        # the charge and the payment if eccluding voids
        # the charged, transfer, void_transfer, and the payment if not
        charge_entry = self.charge_txn.entries.get(
            ledger=self.entity_invoice_1.ledger)
        transfer_entry = self.transfer_txn.entries.get(
            ledger=self.entity_invoice_1.ledger)
        void_transfer_entry = transfer_entry.transaction.voided_by.entries.get(
            ledger=self.entity_invoice_1.ledger)
        payment_entry = self.payment_txn.entries.get(
            ledger=self.entity_invoice_1.ledger)

        entries = self.entity_invoice_2.get_ledger_entries(True)
        self.assertIn(charge_entry, entries)
        self.assertIn(payment_entry, entries)

        entries = self.entity_invoice_2.get_ledger_entries(False)
        self.assertIn(charge_entry, entries)
        self.assertIn(transfer_entry, entries)
        self.assertIn(void_transfer_entry, entries)
        self.assertIn(payment_entry, entries)

    def test_user_invoice_1_has_customer_responsibility(self):
        self.assertEqual(self.user_invoice_1.amount,
                         self.customer_responsibility)

    def test_user_invoice_2_no_customer_responsibility(self):
        self.assertEqual(self.user_invoice_2.amount, 0)

    def test_entity_invoice_1_no_entity_responsibility(self):
        # No respnosibility here because it was transferred to the customer.
        self.assertEqual(self.entity_invoice_1.amount, 0)

    def test_entity_invoice_2_no_entity_responsibility(self):
        # No respnosibility here because it includes the payment!
        self.assertEqual(self.entity_invoice_2.amount, 0)

    def test_regenerate_user_invoice_1(self):
        invoice = Invoice(
            self.user,
            timestamp=self.user_invoice_1.timestamp,
            creation_timestamp=self.user_invoice_1.creation_timestamp)
        self.assertEqual(list(invoice.get_ledger_entries()),
                         list(self.user_invoice_1.get_ledger_entries()))
        self.assertEqual(invoice, self.user_invoice_1)

    def test_user_invoice_1_later_creation_date_includes_backdated_txn(self):
        # Create a new invoice, using user_invoice_1's posted_timestamp
        invoice = Invoice(
            self.user,
            timestamp=self.user_invoice_1.timestamp)
        self.assertEqual(list(self.user_invoice_2.get_ledger_entries()),
                         list(invoice.get_ledger_entries()))


class TestInvoiceTimeRange(TestInvoicingBase):
    """TODO Invoices may contain only LedgerEntries between two timestamps.

    This is the case for Clinic invoices, but it might be better to handle it
    as a RelatedObject invoice.
    """
    def test_timestamp_lte(self):
        # TODO
        pass


class TestInvoiceByObject(TestInvoicingBase):
    """TODO Invoices may be constraing by a LedgerEntry's related_object."""
    pass
