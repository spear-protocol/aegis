# Transfer amount must be non-negative
non_negative_transfer_amount = \
    """
ALTER TABLE ledger_transfer DROP CONSTRAINT IF EXISTS non_negative_transfer_amount;
ALTER TABLE ledger_transfer ADD CONSTRAINT non_negative_transfer_amount CHECK ("amount" >= 0);
ALTER TABLE ledger_transfer VALIDATE CONSTRAINT non_negative_transfer_amount;
"""

# Transfer delivery state must be consistent (sent -> processed == ~sent or processed)
only_processed_transfers_may_be_sent = \
    """
ALTER TABLE ledger_transfer DROP CONSTRAINT IF EXISTS only_processed_transfers_may_be_sent;
ALTER TABLE ledger_transfer ADD CONSTRAINT only_processed_transfers_may_be_sent CHECK ((amount_swapped IS NOT NULL) OR (NOT complete) OR processed);
ALTER TABLE ledger_transfer VALIDATE CONSTRAINT only_processed_transfers_may_be_sent;
"""

# New transfers may not overspend
only_transferrable_amounts_may_be_sent = \
    """
CREATE OR REPLACE FUNCTION check_transfer_amount() RETURNS TRIGGER AS $$
    DECLARE
        deposited_amount NUMERIC(80, 0);
        withdrawing_amount NUMERIC(80, 0);
        balance_amount NUMERIC(80, 0) := 0;
        active_state_amount NUMERIC(80, 0);
    BEGIN
        SELECT SUM(amount) INTO deposited_amount
        FROM ledger_deposit
        WHERE wallet_id = NEW.wallet_id
        AND eon_number = NEW.eon_number;
        
        SELECT SUM(amount) INTO withdrawing_amount
        FROM ledger_withdrawalrequest
        WHERE wallet_id = NEW.wallet_id
        AND eon_number = NEW.eon_number;
        
        SELECT (b.right - b.left) INTO balance_amount
        FROM ledger_exclusivebalanceallotment b
        WHERE b.wallet_id = NEW.wallet_id
        AND b.eon_number = NEW.eon_number;
        
        SELECT (updated_gains - updated_spendings) INTO active_state_amount
        FROM ledger_activestate
        WHERE wallet_id = NEW.wallet_id
        AND eon_number = NEW.eon_number
        AND id = NEW.sender_active_state_id;
        
        IF deposited_amount - withdrawing_amount + balance_amount + active_state_amount < 0 THEN
            RAISE EXCEPTION 'Overspending transaction';
        END IF;
        
        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS only_transferrable_amounts_may_be_sent ON ledger_transfer CASCADE;
CREATE CONSTRAINT TRIGGER only_transferrable_amounts_may_be_sent
AFTER INSERT OR UPDATE
ON ledger_transfer
DEFERRABLE
INITIALLY DEFERRED
FOR EACH ROW
EXECUTE PROCEDURE check_transfer_amount();
"""

# Transfer swap flag should be true if and only if amount_swapped is not null
swap_flag = \
    """
ALTER TABLE ledger_transfer DROP CONSTRAINT IF EXISTS swap_flag;
ALTER TABLE ledger_transfer ADD CONSTRAINT swap_flag CHECK (swap = (amount_swapped IS NOT NULL));
ALTER TABLE ledger_transfer VALIDATE CONSTRAINT swap_flag;
"""
# TODO transfer active state updates must make sense (sender, then recipient, then operator signs both atomically)
