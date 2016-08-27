class TransactionException(Exception):
    pass


class TransactionBalanceException(TransactionException):
    pass


class UnvoidableTransactionException(TransactionException):
    pass


class UnmodifiableTransactionException(TransactionException):
    pass


class PrimaryRelatedObjectException(TransactionException):
    pass


class NoLedgerEntriesException(TransactionException):
    pass


class ExistingLedgerEntriesException(TransactionException):
    pass
