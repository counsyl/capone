# Ledger

`Ledger` is a library that provides double-entry bookkeeping (the foundation of
all modern accounting) for Django with the ability to link each journal entry
to zero or more other Django models as evidence for the transaction.


## Quick Start

### Creating Ledgers

Let's start by creating two common ledger types, "Accounts Receivable" and
"Revenue", which usually have transactions between themselves:

```
In [1]: from ledger.models import Ledger

In [1]: ar = Ledger.objects.create(name='Accounts Receivable', number=1, increased_by_debits=True)
Out[1]: <Ledger: Ledger Accounts Receivable>

In [2]: revenue = Ledger.objects.create(name='Revenue', number=2, increased_by_debits=True)
Out[2]: <Ledger: Ledger Revenue>
```

Both of these accounts are asset accounts, so they're both increased by debits.


### Faking Evidence Models

Now let's create a fake order, so that we have some evidence for these ledger
entries, and a fake user, so we have someone to blame for these transactions:

```
In [3]: from ledger.tests.factories import OrderFactory

In [4]: order = OrderFactory()

In [5]: from ledger.tests.factories import UserFactory

In [6]: user = UserFactory()
```


### Creating Transactions

We're now ready to create a simple transaction:

```
In [7]: from ledger.api.actions import create_transaction

In [8]: from ledger.api.actions import credit

In [9]: from ledger.api.actions import debit

In [10]: from decimal import Decimal

In [11]: from ledger.models import LedgerEntry

In [12]: txn = create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])

In [13]: txn.summary()
Out[13]:
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
In [14]: create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(101)), ledger=revenue)])
---------------------------------------------------------------------------
TransactionBalanceException               Traceback (most recent call last)

[...]

TransactionBalanceException: Credits do not equal debits. Mis-match of -1.
```

So the consistency required of double-entry bookkeeping is automatically kept.

There are many other options for `create_transaction`: see below or its
docstring for details.


### Ledger Balances

`ledger` keeps track of the balance in each ledger for each evidence object in a denormalized and efficient way.  Let's use this behavior to get the balances of our ledgers as well as the balances in each ledger for our `order` object:


```
In [15]: from ledger.api.queries import get_balances_for_object

In [16]: get_balances_for_object(order)
Out[16]: defaultdict(<function <lambda> at 0x7fd7ecfa96e0>, {<Ledger: Ledger Accounts Receivable>: Decimal('100.0000'), <Ledger: Ledger Revenue>: Decimal('-100.0000')})

In [45]: ar.get_balance()
Out[45]: Decimal('100.0000')

In [46]: revenue.get_balance()
Out[46]: Decimal('-100.0000')
```


### Voiding Transactions

We can also void that transaction, which enters a transaction with the same evidence but with all values of the opposite sign:

```
In [15]: void = void_transaction(txn, user)
Out[15]: <Transaction: Transaction 9cd85014-c588-43ff-9532-a6fc2429069e>

In [16]: void_transaction(txn, user)
---------------------------------------------------------------------------
UnvoidableTransactionException            Traceback (most recent call last)

[...]

UnvoidableTransactionException: Cannot void the same Transaction #(e0842107-3a5b-4487-9b86-d1a5d7ab77b4) more than once.

In [17]: void.summary()
Out[17]:
{u'entries': ['LedgerEntry: $-100.0000 in Accounts Receivable',
  'LedgerEntry: $100.0000 in Revenue'],
 u'related_objects': ['TransactionRelatedObject: Order(id=1)']}

In [18]: txn.voids

In [19]: void.voids
Out[19]: <Transaction: Transaction e0842107-3a5b-4487-9b86-d1a5d7ab77b4>
```

Note the new balances for evidence objects and `Ledgers`:

```
In [20]: get_balances_for_object(order)
Out[20]: defaultdict(<function <lambda> at 0x7fd7ecfa9758>, {<Ledger: Ledger Accounts Receivable>: Decimal('0.0000'), <Ledger: Ledger Revenue>: Decimal('0.0000')})

In [21]: ar.get_balance()
Out[21]: Decimal('0.0000')

In [22]: revenue.get_balance()
Out[22]: Decimal('0.0000')
```


### Transaction Types

You can label a `Transaction` using a foreign key to the `TransactionType` to,
say, distinguish between manually made `Transactions` and those made by a bot,
or between `Transactions` that represent two different types of financial
transaction, such as "Reconciliation" and "Revenue Recognition".

By default, `Transactions` are of a special, auto-generated "manual" type:

```
In [23]: txn.type
Out[23]: <TransactionType: Transaction Type Manual>
``` 

but you can create and assign `TransactionTypes` when creating `Transactions`:

```
In [24]: from ledger.models import TransactionType

In [25]: new_type = TransactionType.objects.create(name='New type')

In [26]: txn = create_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)], type=new_type)

In [27]: txn.type
Out[27]: <TransactionType: Transaction Type New type>
```


### Querying Transactions

#### Getting Balances

`Transaction` has a `summary` method to summarize the data on the many models that can link to it:

```
In [62]: txn.summary()
Out[62]:
{u'entries': ['LedgerEntry: $100.0000 in Accounts Receivable',
  'LedgerEntry: $-100.0000 in Revenue'],
 u'related_objects': ['TransactionRelatedObject: Order(id=1)']}
```

To get the balance for a `Ledger`, use its `get_balance` method:

```
In [60]: ar.get_balance()
Out[60]: Decimal('100.0000')
```

To efficiently get the balance of all transactions with a particular object as
evidence, use `get_balances_for_objects`:

```
In [61]: get_balances_for_object(order)
Out[61]: defaultdict(<function <lambda> at 0x7fd7ecfa9230>, {<Ledger: Ledger Accounts Receivable>: Decimal('100.0000'), <Ledger: Ledger Revenue>: Decimal('-100.0000')})
```

`Transactions` are validated before they are created, but if you need to do
this manually for some reason, use the `validate_transaction` function, which
has the same prototype as `create_transaction`:

```
In [63]: validate_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)], type=new_type)

In [64]: validate_transaction(user, evidence=[order], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(101)), ledger=revenue)], type=new_type)
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
In [66]: Transaction.objects.count()
Out[66]: 5

In [67]: Transaction.objects.filter_by_related_objects([order]).count()
Out[67]: 5

In [68]: order2 = OrderFactory()

In [69]: create_transaction(user, evidence=[order2], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
Out[69]: <Transaction: Transaction 68a4adb1-b898-493f-b5f3-4fe7132dd28d>

In [70]: Transaction.objects.filter_by_related_objects([order2]).count()
Out[70]: 1
```

`filter_by_related_objects` is defined on a custom `QuerySet` provided for
`Transaction`, so calls to it can be chained like ordinary `QuerySet` function
calls:

```
In [71]: create_transaction(user, evidence=[order2], ledger_entries=[LedgerEntry(amount=debit(Decimal(100)), ledger=ar), LedgerEntry(amount=credit(Decimal(100)), ledger=revenue)])
Out[71]: <Transaction: Transaction 92049712-4982-4718-bc71-a405b0d762ac>

In [72]: Transaction.objects.filter_by_related_objects([order2]).count()
Out[72]: 2

In [73]: Transaction.objects.filter_by_related_objects([order2]).filter(transaction_id='92049712-4982-4718-bc71-a405b0d762ac').count()
Out[73]: 1
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

```

See `ledger.tests.test_assert_transaction_in_ledgers_for_amounts_with_evidence`
for more examples.


## Introduction

what is it?  mention double-entry, the fact that this library allows you to add "evidence" to transactions, and that it has a rich query API

give a quick overview of what's in this document
    -   why you would want to keep ledgers
    -   double entry, history and practice
    -   how to use leder for basic stuff
    -   an example on reconciliation, a more complex operation that uses evidence

## Principles

some of these might become sections in their own right

-   history of double entry
-   why would you use double entry
-   accounting equation
-   each ledger has a "type": increased or decreased by debits
-   sign conventions of credits and debits (or you can keep them in two columns)
-   implementation detail: it would be more agnostic to hav a "credit/debit" flag, but harder to do sums
-   non-code example of buying something
-   non-code exampleof selling something
-   how each of these ideas is implemented in code

-   somehow you'll have to explain "recognizing revenue" in here, i think, or our examples won't make sense.


## Examples

### Record-Keeping Examples

-   code example of buying something
-   code exampleof selling something

now, let's get into some of the more complex bookkeeping schemes we use at counsyl

-   credit card transactions with fees, etc.
-   reconciling bulk payments from insurance companies into their constituate payments
-   monthly closes and carry-over balances

### Query Examples

-   getting full ledger totals for an item
-   implementation detail: explain LedgerBalance
-   getting unreconciled samples
-   writing tests with `assert_ledger_entries`
