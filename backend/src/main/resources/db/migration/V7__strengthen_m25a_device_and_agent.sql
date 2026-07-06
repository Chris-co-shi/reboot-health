DO $$
BEGIN
    IF EXISTS (
        SELECT code_hash
        FROM bootstrap_session
        GROUP BY code_hash
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'bootstrap_session has duplicate code_hash values before adding uniqueness';
    END IF;

    IF EXISTS (
        SELECT code_hash
        FROM pairing_session
        GROUP BY code_hash
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'pairing_session has duplicate code_hash values before adding uniqueness';
    END IF;
END $$;

ALTER TABLE pairing_session
    DROP COLUMN qr_payload;

CREATE UNIQUE INDEX uk_bootstrap_session_code_hash
    ON bootstrap_session(code_hash);

CREATE UNIQUE INDEX uk_pairing_session_code_hash
    ON pairing_session(code_hash);

CREATE TABLE credential_response_envelope (
    id UUID PRIMARY KEY,
    operation_type VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    encrypted_response TEXT NOT NULL,
    nonce VARCHAR(64) NOT NULL,
    encryption_key_version VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uk_credential_response_envelope_key UNIQUE (idempotency_key),
    CONSTRAINT ck_credential_response_envelope_hash
        CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_credential_response_envelope_expiry
        CHECK (expires_at > created_at),
    CONSTRAINT ck_credential_response_envelope_operation
        CHECK (btrim(operation_type) <> ''),
    CONSTRAINT ck_credential_response_envelope_ciphertext
        CHECK (btrim(encrypted_response) <> '' AND btrim(nonce) <> '')
);
