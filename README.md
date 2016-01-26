# Ledger

The concepts behind ledgers and double entry bookkeeping are several hundred
years old, so there must be something to it. At its core, the idea is simple:

1. Maintain a ledger with three primary columns
    1. Accounts Receivable (AR)
    2. Revenue
    3. Cash
2. Break each column into Debits and Credits
3. Any time you credit one account, you must debit one or more others such that
they cancel out, or "balance"

That's pretty much all there is to it.

## A simple example

Say we run ACME, Inc and we have a customer, Wile E. At a low level of detail
we actually have a new ledger for every customer. In paper Ledgers this is
often just condensed down into a single ledger, but we don't have the
constraints of paper!)

Note that the default convention in `ledger` is to store debits as positive
numbers and credits as negative numbers.  This convention is common but
completely arbitrary.  If you want to switch the convention around, you can set
`DEBITS_ARE_NEGATIVE` to `True` in your settings.py file.  By default, that
constant doesn't need to be defined, and if it remains undefined, `ledger` will
interpret its value as `False`.

### Charges
Let's record a charge of $900 to Wile E.

```python
# Imports and setup
from django.contrib.auth.models import User
from counsyl.product.order.models import Product
from ledger.api.actions import Charge
from ledger.api.actions import TransactionContext

wilee = User.objects.latest('id')
product = Product.objects.earliest('id')

# Business logic
with TransactionContext(product, wilee) as txn:
    txn.record(Charge(wilee, 900))
```

Here you see the two important concepts of the Ledger system:
TransactionContexts and Actions. TransactionContexts
are used to wrap a series of Actions into a single Transaction. They also
perform necessary validation to ensure that credits and debits balance. In
this example, `Charge` is the action we performed. It records a charge against
wilee for $900.

If we were to have written this on paper, you would see that this was actually
recorded as a debit to AR and a credit to Revenue:

<table>
<tr>
  <td>&nbsp;</td>
  <td colspan=2>AR</td>
  <td colspan=2>Rev</td>
  <td colspan=2>Cash</td>
</tr>
<tr>
  <td>&nbsp;</td>
  <td>D</td>
  <td>C</td>
  <td>D</td>
  <td>C</td>
  <td>D</td>
  <td>C</td>
</tr>
<tr>
  <td>Charge</td>
  <td>900</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
  <td>900</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
</tr>
</table>

We can also see that this transaction balances because the sum of credits ==
the sum of debits.

### Invoices

We can send Wile E. an Invoice whenever we want.

```python
from ledger.api.invoice import Invoice

invoice = Invoice(wilee)
print(invoice.amount)
# Decimal('900.0000')
```

An invoice tells you the amount a given entity owes and also gives you a
list of LedgerEntries that are relevant to the Invoice.

```python
print(invoice.get_ledger_entries())
# [<LedgerEntry: LedgerEntry (a076c129165449ce82f5344aa7b24b56) Charge for $900.0000>]
```

The `get_ledger_entries` method accepts a parameter `exclude_voids` that, when
True, returns only those entries which haven't been voided and, when True,
returns all Ledger Entries.

```python
with TransactionContext(product, wilee) as txn:
    txn.record(Charge(wilee, 100))

invoice = Invoice(wilee)
print(invoice.get_ledger_entries())
# [<LedgerEntry: LedgerEntry (a076c129165449ce82f5344aa7b24b56) Charge for $900.0000>, <LedgerEntry: LedgerEntry (6e6a903640be44b9b79fda2e4cdc313d) Charge for $100.0000>]

# Let's undo that charge
from ledger.api.actions import VoidTransaction
VoidTransaction(txn.transaction, wilee).record()
invoice = Invoice(wilee)
print(invoice.get_ledger_entries())
# [<LedgerEntry: LedgerEntry (a076c129165449ce82f5344aa7b24b56) Charge for $900.0000>]
print(invoice.get_ledger_entries(exclude_voids=False))
# [<LedgerEntry: LedgerEntry (a076c129165449ce82f5344aa7b24b56) Charge for $900.0000>, <LedgerEntry: LedgerEntry (6e6a903640be44b9b79fda2e4cdc313d) Charge for $100.0000>, <LedgerEntry: LedgerEntry (c7ae70b6acda417a98373fe55645a2e0) VoidTransaction for $-100.0000>]
```

### Payments
Wile E. gets the invoice and send us the equivalent amount in Bitcoin, which
we immediately sell. Due to Chinese speculation the value of Bitcoin went
through the roof in the time if took his transaction to clear. We cash out
$1000 worth of bitcoin into USD. Now we owe Wile E. a refund!

```python
from ledger.api.actions import Payment
with TransactionContext(product, wilee) as txn:
    txn.record(Payment(wilee, 1000))
```

Behind the scenes a `Payment` credits AR and debits Cash.

<table>
<tr>
  <td>&nbsp;</td>
  <td colspan=2>AR</td>
  <td colspan=2>Rev</td>
  <td colspan=2>Cash</td>
</tr>
<tr>
  <td>&nbsp;</td>
  <td>D</td>
  <td>C</td>
  <td>D</td>
  <td>C</td>
  <td>D</td>
  <td>C</td>
</tr>
<tr>
  <td>Charge</td>
  <td>900</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
  <td>900</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
</tr>
<tr>
  <td>Payment</td>
  <td>&nbsp;</td>
  <td>1000</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
  <td>1000</td>
  <td>&nbsp;</td>
</tr>
</table>

Here again the credits == debits.

### Refunds
How do we know that we now owe Wile E a refund? Simple - the sum of credits
to AR are larger than the sum of debits to AR. If we generate an invoice,
we see that it's negative indicating we owe a refund:

```python
invoice = Invoice(wilee)
print(invoice.amount)
# Decimal('-100.0000')
print(invoice.get_ledger_entries())
# [<LedgerEntry: LedgerEntry (a076c129165449ce82f5344aa7b24b56) Charge for $900.0000>, <LedgerEntry: LedgerEntry (1757f16763154292a1285498c87e4532) Payment for $-1000.0000>]
```

Recording a refund is easy

```python
from ledger.api.actions import Refund
with TransactionContext(product, wilee) as txn:
    txn.record(Refund(wilee, -1 * invoice.amount))

invoice = Invoice(wilee)
print(invoice.amount)
# Decimal('0.0000')
print(invoice.get_ledger_entries())
# [<LedgerEntry: LedgerEntry (a076c129165449ce82f5344aa7b24b56) Charge for $900.0000>, <LedgerEntry: LedgerEntry (1757f16763154292a1285498c87e4532) Payment for $-1000.0000>, <LedgerEntry: LedgerEntry (565d9318594840b69690fdee11f48679) Refund for $100.0000>]
```

Refunds credit Cash and debit AR.

<table>
<tr>
  <td>&nbsp;</td>
  <td colspan=2>AR</td>
  <td colspan=2>Rev</td>
  <td colspan=2>Cash</td>
</tr>
<tr>
  <td>&nbsp;</td>
  <td>D</td>
  <td>C</td>
  <td>D</td>
  <td>C</td>
  <td>D</td>
  <td>C</td>
</tr>
<tr>
  <td>Charge</td>
  <td>900</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
  <td>900</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
</tr>
<tr>
  <td>Payment</td>
  <td>&nbsp;</td>
  <td>1000</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
  <td>1000</td>
  <td>&nbsp;</td>
</tr>
<tr>
  <td>Refund</td>
  <td>100</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
  <td>&nbsp;</td>
  <td>100</td>
</tr>
<tr>
  <td>Sum</td>
  <td colspan=2>0</td>
  <td colspan=2>-900</td>
  <td colspan=2>900</td>
</tr>
</table>

Note that, internally, credits are negative and debits are positive. Yes, it's
weird to think of Revenue being recorded as a negative number, but just
remember there is no spoon. Also note that the Sums at the end still balance.


# Local Development

## Setup:

First, you must set up your working environment:

    make setup

This will build a local virtualenv and all other requirements for local
development.


## Running Commands:

### Makefile

Runserver:

    make runserver

Shell(plus):

    make shell


### `manage.py` commands

Note: before any of these instructions, you may have to run `make develop` to
set up a postgres database for this app.

First, activate a virtualenv so that your commands have access to the
environment built by `make setup`:

From the repository root, run:

    source .venv/bin/activate

Then you should be free to run

    ./manage.py makemigrations --settings=ledger.tests.settings

or any other `manage.py` command, even those in the Makefile.

To run individual tests, use the following:

    ./manage.py test --settings=ledger.tests.settings ledger.tests

Notice the `--settings=ledger.tests.settings` argument: because this repository
is a django sub-module, it wouldn't make sense for it to come with its own
default `settings.py` file.  Instead, it ships with one used to run its tests.
To use `manage.py`, we have to pass an import path to it explicitly.


# API

This common setup is necessary to run the following examples:

```python
# Imports and setup
from datetime import datetime
from datetime import timedelta
from django.contrib.auth.models import User
from counsyl.product.order.models import Product
from ledger.api.actions import Charge
from ledger.api.actions import Payment
from ledger.api.actions import Refund
from ledger.api.actions import TransactionContext
from ledger.api.actions import TransferAmount
from ledger.api.actions import WriteDown
from ledger.api.actions import VoidTransaction

entity = User.objects.earliest('?')
user = User.objects.latest('id')
product = Product.objects.latest('id')
```

## Transactions

TransactionContexts wrap every single action that can create LedgerEntries on a
Ledger and put them in the same Transaction. TransactionContexts act as context
managers that perform necessary validation to ensure that credits and debits
balance. 

TransactionContexts have two required arguments:

* related_object - The object that caused this Transaction to be generated
* created_by - The `User` that caused this Transaction to be generated

and one optional argument:

* posted_timestamp - The (assumed UTC) datetime that this transaction
  was posted in an outside system. If not provided, the current UTC time is
  used

At its most basic, a TransactionContext looks like this:

```python
with TransactionContext(product, user) as txn:
    txn.record(Charge(entity, 1000))
```

A TransactionContext can also contain many different actions:

```python
with TransactionContext(product, user) as txn:
    txn.record(Charge(entity, 1000))
    txn.record(WriteDown(entity, 100))  # Good customer discount
```

### Backdating Transactions

Sometimes we got paid a while ago but we didn't get notification of payment.
In these cases it's helpful to backdate the payment:

```python
backdate_timestamp = datetime.now() - timedelta(days=10)
with TransactionContext(product, user, posted_timestamp=backdate_timestamp) as txn:
    txn.record(Payment(entity, 1000))
```

### Voiding Transactions

TransactionContexts are context managers that give you a reference to the backing
financial transaction in the database (via the `transaction` attribute). This
is useful when you need to, say, void a transaction:

```python
with TransactionContext(product, user) as charge_txn:
    charge_txn.record(Charge(entity, 1000))

VoidTransaction(charge_txn.transaction, user).record()
```

## LedgerEntryActions

All actions which can be performed on a ledger are exposed as a subclass of
`LedgerEntryAction`. All LedgerEntryActions must be performed inside a
TransactionContext.

The two types of LedgerEntryActions are

1. SingleEntityLedgerEntryAction, comprised of:
    1. Charge
    2. Payment
    3. Refund
    4. WriteDown
2. TransferAmount

All LedgerEntryActions expose a `get_ledger_entries` method, which is called by
TransactionContext.record, that returns a list of `LedgerEntry` objects to be added
to the enclosing Transaction.

### SingleEntityLedgerEntryAction

These types of actions have two required arguments in the constructor:

* entity - The entity on whose ledger we are recording an action
* amount - The dollar amount to submit for this action

#### Charge

A Charge debits AR and credits Revenue. Use this to record a charge for
services performed.

```python
with TransactionContext(product, user) as txn:
    txn.record(Charge(entity, 1000))
```

#### Payment

Payments record payments from an entity by crediting AR and debiting Cash. They
are recorded against that entity. The `related_object` for a payment
transaction is important. It is used to determine if that `related_object` has
been fully paid for.

```python
with TransactionContext(product, user) as txn:
    txn.record(Payment(entity, 1000))
```

#### Refund

Refunds credit Cash and debit AR. They are used to record when we refund a
customer.

```python
with TransactionContext(product, user) as txn:
    txn.record(Refund(entity, 1000))
```

#### WriteDown

WriteDowns comp a customer a certain amount. This is typically used for
out-of-pocket max discounts, prompt payment discounts, or as promotions.

```python
with TransactionContext(product, user) as txn:
    txn.record(Charge(entity, 1000))
    txn.record(WriteDown(entity, 100))  # Promotion 1234
```

### TransferAmount

TransferAmount takes three required parameters:

* entity_from - The entity from whose ledger we are decreasing financial
responsibility
* entity_to - The entity who is receiving the financial responsibility
* amount - The dollar amount to submit for this action

```python
with TransactionContext(product, user) as txn:
    txn.record(TransferAmount(entity, user, 500))
```
