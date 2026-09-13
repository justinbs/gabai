CREATE TYPE role AS ENUM ('citizen', 'staff', 'admin');
CREATE TYPE urgency AS ENUM ('low', 'medium', 'high');
CREATE TYPE request_status AS ENUM (
    'submitted', 'classified', 'routed', 'under_review',
    'in_progress', 'resolved', 'closed'
);

CREATE TABLE users (
    id              UUID PRIMARY KEY,
    email           VARCHAR(320) NOT NULL UNIQUE,
    hashed_password VARCHAR(1024) NOT NULL,
    is_active       BOOLEAN NOT NULL,
    is_superuser    BOOLEAN NOT NULL,
    is_verified     BOOLEAN NOT NULL,
    full_name       VARCHAR(150) NOT NULL,
    role            role NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    slug        VARCHAR(50) NOT NULL UNIQUE,
    name        VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    is_active   BOOLEAN NOT NULL
);

CREATE TABLE requests (
    id                    SERIAL PRIMARY KEY,
    reference_number      VARCHAR(20) NOT NULL UNIQUE,
    citizen_id            UUID NOT NULL REFERENCES users(id),
    description           TEXT NOT NULL,
    predicted_category_id INTEGER REFERENCES categories(id),
    predicted_urgency     urgency,
    category_confidence   FLOAT,
    urgency_confidence    FLOAT,
    final_category_id     INTEGER REFERENCES categories(id),
    final_urgency         urgency,
    status                request_status NOT NULL,
    assigned_staff_id     UUID REFERENCES users(id),
    model_version         VARCHAR(100),
    classified_at         TIMESTAMP,
    created_at            TIMESTAMP NOT NULL DEFAULT now(),
    updated_at            TIMESTAMP NOT NULL DEFAULT now(),
    resolved_at           TIMESTAMP
);

CREATE TABLE routing_rules (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    staff_id    UUID NOT NULL REFERENCES users(id),
    is_active   BOOLEAN NOT NULL
);

CREATE TABLE attachments (
    id          SERIAL PRIMARY KEY,
    request_id  INTEGER NOT NULL REFERENCES requests(id),
    filename    VARCHAR(255) NOT NULL,
    stored_path VARCHAR(255) NOT NULL,
    mime_type   VARCHAR(100) NOT NULL,
    size_bytes  INTEGER NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id               SERIAL PRIMARY KEY,
    user_id          UUID NOT NULL REFERENCES users(id),
    request_id       INTEGER REFERENCES requests(id),
    reference_number VARCHAR(20),
    message          TEXT NOT NULL,
    is_read          BOOLEAN NOT NULL,
    created_at       TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE status_history_entries (
    id          SERIAL PRIMARY KEY,
    request_id  INTEGER NOT NULL REFERENCES requests(id),
    from_status request_status,
    to_status   request_status NOT NULL,
    actor_id    UUID REFERENCES users(id),
    note        TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE audit_log_entries (
    id          SERIAL PRIMARY KEY,
    actor_id    UUID REFERENCES users(id),
    action      VARCHAR(100) NOT NULL,
    object_type VARCHAR(50) NOT NULL,
    object_id   VARCHAR(100),
    detail      JSONB,
    ip_address  VARCHAR(45),
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);
