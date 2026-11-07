from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.execute("""
    CREATE TABLE webhook_events (
        event_id TEXT PRIMARY KEY,
        received_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE tickets (
        id BIGSERIAL PRIMARY KEY,
        ticket_id TEXT NOT NULL UNIQUE,
        customer_email TEXT NOT NULL,
        message TEXT NOT NULL,
        reply_url TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'new',
        attempts INTEGER NOT NULL DEFAULT 0,
        locked_until TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_tickets_status ON tickets (status, id);

    CREATE TABLE articles (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        tsv TSVECTOR GENERATED ALWAYS AS
            (to_tsvector('simple', title || ' ' || body)) STORED
    );
    CREATE INDEX ix_articles_tsv ON articles USING GIN (tsv);

    CREATE TABLE drafts (
        id BIGSERIAL PRIMARY KEY,
        ticket_id BIGINT NOT NULL REFERENCES tickets(id),
        body TEXT NOT NULL,
        article_ids INTEGER[] NOT NULL DEFAULT '{}',
        is_mock BOOLEAN NOT NULL DEFAULT false,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE outbound_replies (
        id BIGSERIAL PRIMARY KEY,
        ticket_id BIGINT NOT NULL UNIQUE REFERENCES tickets(id),
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        sent_at TIMESTAMPTZ
    );

    CREATE TABLE rate_limit (
        window_start TIMESTAMPTZ PRIMARY KEY,
        count INTEGER NOT NULL DEFAULT 0
    );
    """)


def downgrade():
    op.execute("""
    DROP TABLE rate_limit, outbound_replies, drafts, articles, tickets, webhook_events;
    """)