# Signature checksum length: 32 bytes, 64 hex encoded characters
fixed_checksum_size = \
    """
ALTER TABLE ledger_signature DROP CONSTRAINT IF EXISTS fixed_checksum_size;
ALTER TABLE ledger_signature ADD CONSTRAINT fixed_checksum_size CHECK (char_length(checksum) = 64);
ALTER TABLE ledger_signature VALIDATE CONSTRAINT fixed_checksum_size;
"""

# Encoded signature value length: 32 + 32 + 1 = 65 bytes, 130 hex encoded characters
fixed_value_size = \
    """
ALTER TABLE ledger_signature DROP CONSTRAINT IF EXISTS fixed_value_size;
ALTER TABLE ledger_signature ADD CONSTRAINT fixed_value_size CHECK (char_length(value) = 130);
ALTER TABLE ledger_signature VALIDATE CONSTRAINT fixed_value_size;
"""

# TODO verify signature value on checksum

# TODO make values immutable
