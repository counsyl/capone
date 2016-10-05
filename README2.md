# Ledger

log line

## Quick Start

Show a quick session of
-   using ledger to create ledgers and transactions with evidence
-   voiding transactions
-   querying over transactions with evidence
-   asserting state of ledgers

```
```

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
