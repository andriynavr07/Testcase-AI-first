from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.execute("""
    ALTER TABLE articles ADD COLUMN slug TEXT NOT NULL;
    CREATE UNIQUE INDEX ux_articles_slug ON articles (slug);
    """)


def downgrade():
    op.execute("""
    DROP INDEX ux_articles_slug;
    ALTER TABLE articles DROP COLUMN slug;
    """)