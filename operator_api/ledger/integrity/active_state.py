# ActiveState spend/gain should be non-negative
non_negative_spend_gain = \
    """
ALTER TABLE ledger_activestate DROP CONSTRAINT IF EXISTS non_negative_spend_gain;
ALTER TABLE ledger_activestate ADD CONSTRAINT non_negative_spend_gain CHECK (
    updated_spendings >= 0 AND updated_gains >= 0);
ALTER TABLE ledger_activestate VALIDATE CONSTRAINT non_negative_spend_gain;
"""

# New active states must monotonically increase the latest eon
spend_and_gain_increase_monotonically = \
    """
CREATE OR REPLACE FUNCTION check_spend_gain_increase() RETURNS TRIGGER AS $$
    DECLARE
        max_spent NUMERIC(80, 0);
        max_gained NUMERIC(80, 0);
    BEGIN
        SELECT MAX(updated_spendings), MAX(updated_gains)
        INTO max_spent, max_gained
        FROM ledger_activestate 
        WHERE id != NEW.id
        AND wallet_id = NEW.wallet_id
        AND eon_number = NEW.eon_number
        AND operator_signature_id IS NOT NULL;
        
        IF coalesce(max_spent, 0) > NEW.updated_spendings THEN
            RAISE EXCEPTION 'Invalid updated spendings';
        END IF;
        IF coalesce(max_gained, 0) > NEW.updated_gains THEN
            RAISE EXCEPTION 'Invalid updated gains';
        END IF;
        
        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS spend_and_gain_increase_monotonically ON ledger_activestate CASCADE;
CREATE CONSTRAINT TRIGGER spend_and_gain_increase_monotonically
AFTER INSERT OR UPDATE
ON ledger_activestate
NOT DEFERRABLE
INITIALLY IMMEDIATE
FOR EACH ROW
EXECUTE PROCEDURE check_spend_gain_increase();
"""

# TODO define stored procedures to replace general updates with correct updates only
