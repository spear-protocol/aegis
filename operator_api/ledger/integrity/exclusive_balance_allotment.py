# Balance boundaries must be non-negative and locally ordered
non_negative_locally_ordered_bounds = \
    """
ALTER TABLE ledger_exclusivebalanceallotment DROP CONSTRAINT IF EXISTS non_negative_locally_ordered_bounds;
ALTER TABLE ledger_exclusivebalanceallotment ADD CONSTRAINT non_negative_locally_ordered_bounds CHECK ("left" >= 0 AND "right" >= "left");
ALTER TABLE ledger_exclusivebalanceallotment VALIDATE CONSTRAINT non_negative_locally_ordered_bounds;
"""

# Exclusive allotment eon must be non negative
non_negative_eon_number = \
    """
ALTER TABLE ledger_exclusivebalanceallotment DROP CONSTRAINT IF EXISTS non_negative_eon_number;
ALTER TABLE ledger_exclusivebalanceallotment ADD CONSTRAINT non_negative_eon_number CHECK ("eon_number" >= 0);
ALTER TABLE ledger_exclusivebalanceallotment VALIDATE CONSTRAINT non_negative_eon_number;
"""

# Balance boundaries must be non-intersecting
non_intersecting_boundaries = \
    """
CREATE OR REPLACE FUNCTION check_intersecting_boundary() RETURNS TRIGGER AS $$
    DECLARE
        number_of_intersecting_intervals INT;
        target_token_id INT;
    BEGIN
        SELECT ledger_wallet.token_id INTO target_token_id
        FROM ledger_wallet
        WHERE id = NEW.wallet_id;

        SELECT COUNT(*) INTO number_of_intersecting_intervals
        FROM ledger_exclusivebalanceallotment
        LEFT JOIN ledger_wallet
        ON ledger_exclusivebalanceallotment.wallet_id = ledger_wallet.id
        WHERE (ledger_exclusivebalanceallotment.id != NEW.id
        AND ledger_wallet.token_id = target_token_id
        AND ledger_exclusivebalanceallotment.eon_number = NEW.eon_number
        AND (
            (NEW.left = NEW.right AND ledger_exclusivebalanceallotment.left < NEW.left AND NEW.left < ledger_exclusivebalanceallotment.right)
            OR
            (NEW.left < NEW.right AND ledger_exclusivebalanceallotment.left = ledger_exclusivebalanceallotment.right AND NEW.left < ledger_exclusivebalanceallotment.left AND ledger_exclusivebalanceallotment.left < NEW.right)
            OR
            (NEW.left < NEW.right AND ledger_exclusivebalanceallotment.left < ledger_exclusivebalanceallotment.right AND (
                        (NEW.left <= ledger_exclusivebalanceallotment.left AND ledger_exclusivebalanceallotment.left < NEW.right)
                        OR
                        (NEW.left < ledger_exclusivebalanceallotment.right AND ledger_exclusivebalanceallotment.right < NEW.right)
                        OR
                        (ledger_exclusivebalanceallotment.left <= NEW.left AND NEW.left < ledger_exclusivebalanceallotment.right)
                        OR
                        (ledger_exclusivebalanceallotment.left < NEW.right AND NEW.right < ledger_exclusivebalanceallotment.right)
            ))
        ));

        IF number_of_intersecting_intervals != 0 THEN
            RAISE EXCEPTION 'Intersecting boundaries';
        END IF;
        
        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS non_intersecting_boundaries ON ledger_exclusivebalanceallotment CASCADE;
CREATE CONSTRAINT TRIGGER non_intersecting_boundaries
AFTER INSERT OR UPDATE
ON ledger_exclusivebalanceallotment
NOT DEFERRABLE
INITIALLY IMMEDIATE
FOR EACH ROW
EXECUTE PROCEDURE check_intersecting_boundary();
"""

# Balance boundaries must be continuous
continuous_boundaries = \
    """
CREATE OR REPLACE FUNCTION check_continuous_boundary() RETURNS TRIGGER AS $$
    DECLARE
        number_of_adjacent_intervals INT;
        number_of_intervals_in_eon INT;
        target_token_id INT;
    BEGIN
        SELECT ledger_wallet.token_id INTO target_token_id
        FROM ledger_wallet
        WHERE id = NEW.wallet_id;

        SELECT COUNT(*) INTO number_of_adjacent_intervals
        FROM ledger_exclusivebalanceallotment
        LEFT JOIN ledger_wallet
        ON ledger_exclusivebalanceallotment.wallet_id = ledger_wallet.id
        WHERE ledger_exclusivebalanceallotment.id != NEW.id
        AND ledger_wallet.token_id = target_token_id
        AND ledger_exclusivebalanceallotment.eon_number = NEW.eon_number
        AND (
            NEW.left = ledger_exclusivebalanceallotment.right 
            OR
            NEW.right = ledger_exclusivebalanceallotment.left);
        

        IF number_of_adjacent_intervals = 0 THEN
            SELECT COUNT(*) INTO number_of_intervals_in_eon
            FROM ledger_exclusivebalanceallotment
            LEFT JOIN ledger_wallet
            ON ledger_exclusivebalanceallotment.wallet_id = ledger_wallet.id
            WHERE ledger_exclusivebalanceallotment.eon_number = NEW.eon_number
            AND ledger_wallet.token_id = target_token_id;
            
            IF number_of_intervals_in_eon > 1 THEN
                RAISE EXCEPTION 'Non-adjacent boundaries';
            END IF;
        END IF;
        
        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS continuous_boundaries ON ledger_exclusivebalanceallotment CASCADE;
CREATE CONSTRAINT TRIGGER continuous_boundaries
AFTER INSERT OR UPDATE
ON ledger_exclusivebalanceallotment
NOT DEFERRABLE
INITIALLY IMMEDIATE
FOR EACH ROW
EXECUTE PROCEDURE check_continuous_boundary();
"""

# TODO balance must sum up to <= known contract balance
