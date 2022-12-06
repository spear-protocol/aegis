# Withdrawal amount must be non-negative
non_negative_amount = \
    """
ALTER TABLE ledger_withdrawal DROP CONSTRAINT IF EXISTS non_negative_amount;
ALTER TABLE ledger_withdrawal ADD CONSTRAINT non_negative_amount CHECK ("amount" >= 0);
ALTER TABLE ledger_withdrawal VALIDATE CONSTRAINT non_negative_amount;
"""
