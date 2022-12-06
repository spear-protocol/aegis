# Wallet address length should be 20 bytes = 40 characters in hex encoding
fixed_address_size = \
    """
ALTER TABLE ledger_wallet DROP CONSTRAINT IF EXISTS fixed_address_size;
ALTER TABLE ledger_wallet ADD CONSTRAINT fixed_address_size CHECK (char_length(address) = 40);
ALTER TABLE ledger_wallet VALIDATE CONSTRAINT fixed_address_size;
"""

# Wallet registration eon should be non-negative
non_negative_registration_eon_number = \
    """
ALTER TABLE ledger_wallet DROP CONSTRAINT IF EXISTS non_negative_registration_eon_number;
ALTER TABLE ledger_wallet ADD CONSTRAINT non_negative_registration_eon_number CHECK (registration_eon_number >= 0);
ALTER TABLE ledger_wallet VALIDATE CONSTRAINT non_negative_registration_eon_number;
"""

# Registered wallets must have signed admission authorizations attached
registration_must_be_provable = \
    """
CREATE OR REPLACE FUNCTION check_registration_proof() RETURNS TRIGGER AS $$
    DECLARE
      registration_authorization_id INT := NULL;
    BEGIN
        SELECT w.registration_authorization_id INTO registration_authorization_id 
        FROM ledger_wallet w WHERE w.id = NEW.id;
        
        IF registration_authorization_id IS NULL THEN
            RAISE EXCEPTION 'Missing registration proof.';
        END IF;

        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS registration_must_be_provable ON ledger_wallet CASCADE;
CREATE CONSTRAINT TRIGGER registration_must_be_provable
AFTER INSERT OR UPDATE
ON ledger_wallet
DEFERRABLE
INITIALLY DEFERRED
FOR EACH ROW
EXECUTE PROCEDURE check_registration_proof();
"""

# TODO New Wallet registration eon should be equal to current eon according to State table
