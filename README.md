# Ledger

`Ledger` is a library that provides double-entry bookkeeping (the foundation of
all modern accounting) for Django with the ability to link each journal entry
to zero or more other Django models as evidence for the transaction.

## Introduction

In double-entry bookkeeping, all recordable events (purchases, sales, equipment
depreciation, bad debt markdowns, etc.) are tracked as "ledger entries" or
"transactions" in "ledgers".  Each ledger entry is made up of one or more
"credit" and one or more "debit" entry.  For the sake of this brief example,
you can think of credits as increasing the amount of money recorded in a ledger
and a debit decreasing it.  With that, the central idea behind double-entry
bookkeeping is that the sum of every ledger entry's debits must equal the sum
of its credits.  `ledger` implements a double-entry bookkeeping system by
providing an API for checking that all created entries satisfy this condition
or rolling back the transaction if not.

Where `ledger` transcends other double-entry bookkeeping Django libraries is
that it allows any number of arbitrary objects to be attached, via generic
foreign key, to a ledger entry as "evidence" for that transaction's having
happened.  For instance, a transaction recording a bank deposit from an
insurance company paying for several different medical tests, each at
a different price, could be linked to the original `Order` objects that
triggered the test.  `ledger` also provides an API for the efficient querying
of ledger entries by evidence.

For more information on the concept of double-entry bookkeeping itself, we
recommend the Wikipedia article:
https://en.wikipedia.org/wiki/Double-entry_bookkeeping_system.


## Local Development

### Setup:

First, you must set up your working environment:

    make setup

This will build a local virtualenv and all other requirements for local
development.


### Running Commands:

#### Makefile

Runserver:

    make runserver

Shell(plus):

    make shell


#### `manage.py` commands

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


## Usage

### Creating Ledgers

Let's start by creating two common ledger types, "Accounts Receivable" and
"Revenue", which usually have transactions between themselves:

```
>>> from ledger.models import Ledger
>>> ar = Ledger.objects.create(name='Accounts Receivable', number=1, increased_by_debits=True)
<Ledger: Ledger Accounts Receivable>
>>> revenue = Ledger.objects.create(name='Revenue', number=2, increased_by_debits=True)
<Ledger: Ledger Revenue>
```

Both of these accounts are asset accounts, so they're both increased by debits.
Please consult the double-entry bookkeeping Wikipedia article for a more
in-depth explanation of the "accounting equation" and whether debits increase
or decrease an account.

Also, note that the default convention in `ledger` is to store debits as
positive numbers and credits as negative numbers.  This convention is common
but completely arbitrary.  If you want to switch the convention around, you can
set `DEBITS_ARE_NEGATIVE` to `True` in your settings.py file.  By default, that
constant doesn't need to be defined, and if it remains undefined, `ledger` will
interpret its value as `False`.


### Faking Evidence Models

Now let's create a fake order, so that we have some evidence for these ledger
entries, and a fake user, so we have someone to blame for these transactions:

```
>>> from ledger.tests.factories import OrderFactory
>>> order = OrderFactory()
>>> from ledger.tests.factories import UserFactory
>>> user = UserFactory()
```


### Creating Transactions

We're now ready to create a simple transaction:

```
>>> from ledger.api.actions import create_transaction
>>> from ledger.api.actions import credit
>>> from ledger.api.actions import debit
>>> from decimal import Decimal
>>> from ledger.models import LedgerEntry
>>> txn = create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
>>> txn.summary()
{
    u'entries': [
        'LedgerEntry: $100.0000 in Accounts Receivable',
        'LedgerEntry: $-100.0000 in Revenue',
    ],
    u'related_objects': [
        'TransactionRelatedObject: Order(id=1)',
    ]
}
```

Note that we use the helper functions `credit` and `debit` with positive
numbers to keep the signs consistent in our code.  There should be no reason to
use negative numbers with `ledger`.

Note also that the value for the credit and debit is the same: $100.  If we
tried to create a transaction with mismatching amounts, we would get an error:

```
>>> create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(101)), ledger=revenue)])
---------------------------------------------------------------------------
TransactionBalanceException               Traceback (most recent call last)

[...]

TransactionBalanceException: Credits do not equal debits. Mis-match of -1.
```

So the consistency required of double-entry bookkeeping is automatically kept.

There are many other options for `create_transaction`: see below or its
docstring for details.


### Ledger Balances

`ledger` keeps track of the balance in each ledger for each evidence object in
a denormalized and efficient way.  Let's use this behavior to get the balances
of our ledgers as well as the balances in each ledger for our `order` object:


```
>>> from ledger.api.queries import get_balances_for_object

>>> get_balances_for_object(order)
defaultdict(<function <lambda> at 0x7fd7ecfa96e0>, {<Ledger: Ledger Accounts Receivable>: Decimal('100.0000'), <Ledger: Ledger Revenue>: Decimal('-100.0000')})

>>> ar.get_balance()
Decimal('100.0000')

>>> revenue.get_balance()
Decimal('-100.0000')
```


### Voiding Transactions

We can also void that transaction, which enters a transaction with the same
evidence but with all values of the opposite sign:

```
>>> void = void_transaction(txn, user)
<Transaction: Transaction 9cd85014-c588-43ff-9532-a6fc2429069e>

>>> void_transaction(txn, user)
---------------------------------------------------------------------------
UnvoidableTransactionException            Traceback (most recent call last)

[...]

UnvoidableTransactionException: Cannot void the same Transaction #(e0842107-3a5b-4487-9b86-d1a5d7ab77b4) more than once.

>>> void.summary()
{u'entries': ['LedgerEntry: $-100.0000 in Accounts Receivable',
  'LedgerEntry: $100.0000 in Revenue'],
 u'related_objects': ['TransactionRelatedObject: Order(id=1)']}

>>> txn.voids

>>> void.voids
<Transaction: Transaction e0842107-3a5b-4487-9b86-d1a5d7ab77b4>
```

Note the new balances for evidence objects and `Ledgers`:

```
>>> get_balances_for_object(order)
defaultdict(<function <lambda> at 0x7fd7ecfa9758>, {<Ledger: Ledger Accounts Receivable>: Decimal('0.0000'), <Ledger: Ledger Revenue>: Decimal('0.0000')})

>>> ar.get_balance()
Decimal('0.0000')

>>> revenue.get_balance()
Decimal('0.0000')
```


### Transaction Types

You can label a `Transaction` using a foreign key to the `TransactionType` to,
say, distinguish between manually made `Transactions` and those made by a bot,
or between `Transactions` that represent two different types of financial
transaction, such as "Reconciliation" and "Revenue Recognition".

By default, `Transactions` are of a special, auto-generated "manual" type:

```
>>> txn.type
<TransactionType: Transaction Type Manual>
``` 

but you can create and assign `TransactionTypes` when creating `Transactions`:

```
>>> from ledger.models import TransactionType
>>> new_type = TransactionType.objects.create(name='New type')
>>> txn = create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)], type=new_type)
>>> txn.type
<TransactionType: Transaction Type New type>
```


### Querying Transactions

#### Getting Balances

`Transaction` has a `summary` method to summarize the data on the many models
that can link to it:

```
>>> txn.summary()
{u'entries': ['LedgerEntry: $100.0000 in Accounts Receivable',
  'LedgerEntry: $-100.0000 in Revenue'],
 u'related_objects': ['TransactionRelatedObject: Order(id=1)']}
```

To get the balance for a `Ledger`, use its `get_balance` method:

```
>>> ar.get_balance()
Decimal('100.0000')
```

To efficiently get the balance of all transactions with a particular object as
evidence, use `get_balances_for_objects`:

```
>>> get_balances_for_object(order)
defaultdict(<function <lambda> at 0x7fd7ecfa9230>, {<Ledger: Ledger Accounts Receivable>: Decimal('100.0000'), <Ledger: Ledger Revenue>: Decimal('-100.0000')})
```

`Transactions` are validated before they are created, but if you need to do
this manually for some reason, use the `validate_transaction` function, which
has the same prototype as `create_transaction`:

```
>>> validate_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)], type=new_type)
>>> validate_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(101)), ledger=revenue)], type=new_type)
---------------------------------------------------------------------------
TransactionBalanceException               Traceback (most recent call last)
<ipython-input-64-07b6d139bb37> in <module>()
----> 1 validate_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(101)), ledger=revenue)], type=new_type)

/home/hunter/ledger/ledger/api/queries.pyc in validate_transaction(user, evidence, ledger_entries, notes, type, posted_timestamp)
     67     if total != Decimal(0):
     68         raise TransactionBalanceException(
---> 69             "Credits do not equal debits. Mis-match of %s." % total)
     70
     71     if not ledger_entries:

TransactionBalanceException: Credits do not equal debits. Mis-match of -1.
```

### Queries

Along with the query possibilities from the Django ORM, `ledger` provides
`Transaction.filter_by_related_objects` for finding `Transactions` that are
related to certain models as evidence.

```
>>> Transaction.objects.count()
5

>>> Transaction.objects.filter_by_related_objects([order]).count()
5

>>> order2 = OrderFactory()

>>> create_transaction(user, evidence=[order2], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
<Transaction: Transaction 68a4adb1-b898-493f-b5f3-4fe7132dd28d>

>>> Transaction.objects.filter_by_related_objects([order2]).count()
1
```

`filter_by_related_objects` is defined on a custom `QuerySet` provided for
`Transaction`, so calls to it can be chained like ordinary `QuerySet` function
calls:

```
>>> create_transaction(user, evidence=[order2], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
<Transaction: Transaction 92049712-4982-4718-bc71-a405b0d762ac>

>>> Transaction.objects.filter_by_related_objects([order2]).count()
2

>>> Transaction.objects.filter_by_related_objects([order2]).filter(transaction_id='92049712-4982-4718-bc71-a405b0d762ac').count()
1
```

`filter_by_related_objects` takes an optional `match_type` argument, which is
of type `MatchType(Enum)` that allows one to filter in different ways, namely
whether the matching transactions may have "any", "all", "none", or "exactly"
the evidence provided, determined by `MatchTypes` `ANY`, `ALL`, `NONE`, and
`EXACT`, respectively.


### Asserting over Transactions

For writing tests, the method
`assert_transaction_in_ledgers_for_amounts_with_evidence` is provided for
convenience.  As its name implies, it allows asserting the existence of exactly
one `Transaction` with the ledger amounts, evidence, and other fields on ledger
provided to the method.

```
>>> create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
<Transaction: Transaction b3e73f1d-6b10-4597-b19b-84800839d5b3>
>>> with assert_raises(Transaction.DoesNotExist):
...     assert_transaction_in_ledgers_for_amounts_with_evidence(ledger_amount_pairs=[(revenue.name, credit(Decimal(100))), (ar.name, debit(Decimal(100)))], evidence=[])
...
>>> assert_transaction_in_ledgers_for_amounts_with_evidence(ledger_amount_pairs=[(revenue.name, credit(Decimal(100))), (ar.name, debit(Decimal(100)))], evidence=[order])
>>> with assert_raises(Transaction.DoesNotExist):
...     assert_transaction_in_ledgers_for_amounts_with_evidence(ledger_amount_pairs=[(revenue.name, credit(Decimal(100))), (ar.name, debit(Decimal(100)))], evidence=[order])
...
Traceback (most recent call last):
  File "<console>", line 2, in <module>
    File "/usr/lib/python2.7/unittest/case.py", line 116, in __exit__
        "{0} not raised".format(exc_name))
        AssertionError: DoesNotExist not raised
```

You can see
`ledger.tests.test_assert_transaction_in_ledgers_for_amounts_with_evidence` for
more examples!
