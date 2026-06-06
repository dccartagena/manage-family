"""Food inventory: canonical_products, product_cache, inventory_items, shopping_items FK.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS canonical_products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            is_staple BOOLEAN NOT NULL DEFAULT FALSE,
            usual_location TEXT NOT NULL
                CHECK (usual_location IN ('fridge','freezer','pantry','other')),
            expiry_days_default INTEGER CHECK (expiry_days_default > 0)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS product_cache (
            barcode TEXT PRIMARY KEY,
            canonical_product_id UUID REFERENCES canonical_products(id),
            source TEXT NOT NULL CHECK (source IN ('off','ah','jumbo','manual')),
            name TEXT NOT NULL,
            brand TEXT,
            category TEXT,
            raw_data JSONB NOT NULL DEFAULT '{}',
            cached_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS inventory_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            canonical_product_id UUID NOT NULL REFERENCES canonical_products(id),
            barcode TEXT REFERENCES product_cache(barcode),
            name TEXT NOT NULL,
            location TEXT NOT NULL CHECK (location IN ('fridge','freezer','pantry','other')),
            status TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','low','out')),
            expiry_date DATE,
            added_by UUID NOT NULL REFERENCES persons(id),
            added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            removed_at TIMESTAMPTZ,
            removed_reason TEXT CHECK (removed_reason IN ('used','thrown','transferred'))
        )
    """)

    op.execute("""
        ALTER TABLE shopping_items
        ADD COLUMN canonical_product_id UUID REFERENCES canonical_products(id)
    """)

    op.execute("""
        CREATE INDEX idx_inventory_items_group_active
            ON inventory_items(group_id, location)
            WHERE removed_at IS NULL
    """)
    op.execute("""
        CREATE INDEX idx_inventory_items_expiry
            ON inventory_items(group_id, expiry_date)
            WHERE removed_at IS NULL AND expiry_date IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX idx_shopping_items_canonical
            ON shopping_items(group_id, canonical_product_id)
            WHERE checked = FALSE AND canonical_product_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX idx_canonical_products_group
            ON canonical_products(group_id)
    """)

    op.execute("ALTER TABLE canonical_products ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE product_cache ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE inventory_items ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY canonical_products_group_member ON canonical_products
            FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM memberships
                    WHERE memberships.group_id = canonical_products.group_id
                      AND memberships.person_id = auth.uid()
                )
            )
    """)
    op.execute("""
        CREATE POLICY inventory_items_group_member ON inventory_items
            FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM memberships
                    WHERE memberships.group_id = inventory_items.group_id
                      AND memberships.person_id = auth.uid()
                )
            )
    """)
    op.execute("""
        CREATE POLICY product_cache_read ON product_cache
            FOR SELECT USING (auth.uid() IS NOT NULL)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS product_cache_read ON product_cache")
    op.execute("DROP POLICY IF EXISTS inventory_items_group_member ON inventory_items")
    op.execute("DROP POLICY IF EXISTS canonical_products_group_member ON canonical_products")

    op.execute("ALTER TABLE canonical_products DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE product_cache DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE inventory_items DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS idx_canonical_products_group")
    op.execute("DROP INDEX IF EXISTS idx_shopping_items_canonical")
    op.execute("DROP INDEX IF EXISTS idx_inventory_items_expiry")
    op.execute("DROP INDEX IF EXISTS idx_inventory_items_group_active")

    op.execute("ALTER TABLE shopping_items DROP COLUMN IF EXISTS canonical_product_id")

    op.execute("DROP TABLE IF EXISTS inventory_items CASCADE")
    op.execute("DROP TABLE IF EXISTS product_cache CASCADE")
    op.execute("DROP TABLE IF EXISTS canonical_products CASCADE")
