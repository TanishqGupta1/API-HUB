"""Baseline schema — full production schema as of Phase 13.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-04

UPGRADING AN EXISTING DATABASE
-------------------------------
If your database was created before Alembic adoption, run:

    cd backend && alembic stamp 0001_baseline

This marks the DB as "at baseline" without running any DDL (your tables
already exist).  Future `alembic upgrade head` runs will only apply new
migrations written after this baseline.

FRESH DEPLOYMENTS
-----------------
Run:

    cd backend && alembic upgrade head

All tables are created with IF NOT EXISTS guards so this is idempotent.
"""

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) NOT NULL UNIQUE,
            protocol VARCHAR(50) NOT NULL,
            promostandards_code VARCHAR(100),
            base_url TEXT,
            auth_config TEXT NOT NULL DEFAULT '{}',
            protocol_config JSONB,
            endpoint_cache JSONB,
            endpoint_cache_updated_at TIMESTAMPTZ,
            field_mappings JSONB,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            adapter_class VARCHAR(64),
            last_full_sync TIMESTAMPTZ,
            last_delta_sync TIMESTAMPTZ,
            has_decoration_overlay BOOLEAN NOT NULL DEFAULT FALSE,
            push_name_prefix VARCHAR(32),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            ops_base_url TEXT NOT NULL,
            ops_token_url TEXT NOT NULL,
            ops_client_id VARCHAR(255) NOT NULL,
            ops_auth_config TEXT NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
            external_id VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            parent_id UUID REFERENCES categories(id) ON DELETE SET NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_category_supplier_external UNIQUE (supplier_id, external_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
            supplier_sku VARCHAR(255) NOT NULL,
            product_name VARCHAR(500) NOT NULL,
            brand VARCHAR(255),
            category VARCHAR(255),
            category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
            description TEXT,
            product_type VARCHAR(50) NOT NULL DEFAULT 'apparel',
            image_url TEXT,
            ops_product_id VARCHAR(255),
            external_catalogue INTEGER,
            last_synced TIMESTAMPTZ,
            last_image_fetch_at TIMESTAMPTZ,
            last_image_fetch_attempt_at TIMESTAMPTZ,
            archived_at TIMESTAMPTZ,
            CONSTRAINT uq_product_supplier_sku UNIQUE (supplier_id, supplier_sku)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_archived_at ON products(archived_at)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS product_variants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            color VARCHAR(100),
            size VARCHAR(50),
            sku VARCHAR(255),
            base_price NUMERIC(10,2),
            inventory INTEGER,
            warehouse VARCHAR(255),
            CONSTRAINT uq_product_variants_product_sku UNIQUE (product_id, sku)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_product_id ON product_variants(product_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            supplier_image_url TEXT,
            image_type VARCHAR(50) NOT NULL DEFAULT 'front',
            color VARCHAR(100),
            sort_order INTEGER NOT NULL DEFAULT 0,
            checksum VARCHAR(64),
            CONSTRAINT uq_product_image_url UNIQUE (product_id, url)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_images_product_id ON product_images(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_images_checksum ON product_images(checksum)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS product_options (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            ops_option_id INTEGER,
            master_option_id INTEGER,
            option_key VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            options_type VARCHAR(100),
            sort_order INTEGER NOT NULL DEFAULT 0,
            required BOOLEAN NOT NULL DEFAULT FALSE,
            status INTEGER NOT NULL DEFAULT 1,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            overridden_sort INTEGER,
            CONSTRAINT uq_product_option_key UNIQUE (product_id, option_key)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_options_product_id ON product_options(product_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS product_option_attributes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_option_id UUID NOT NULL REFERENCES product_options(id) ON DELETE CASCADE,
            ops_attribute_id INTEGER,
            master_attribute_id INTEGER,
            attribute_key VARCHAR(255),
            title VARCHAR(255) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 1,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            price NUMERIC(10,2),
            setup_cost NUMERIC(10,2),
            multiplier NUMERIC(10,2),
            numeric_value NUMERIC(10,2),
            overridden_sort INTEGER,
            CONSTRAINT uq_option_attribute_title UNIQUE (product_option_id, title)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS apparel_details (
            product_id UUID PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
            pricing_method VARCHAR(50) NOT NULL DEFAULT 'tiered_variant',
            raw_payload JSONB
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS print_details (
            product_id UUID PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
            pricing_method VARCHAR(50) NOT NULL DEFAULT 'formula',
            min_width NUMERIC(10,2),
            max_width NUMERIC(10,2),
            min_height NUMERIC(10,2),
            max_height NUMERIC(10,2),
            size_unit VARCHAR(10) NOT NULL DEFAULT 'in',
            base_price_per_sq_unit NUMERIC(10,4),
            raw_payload JSONB
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS variant_prices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            variant_id UUID NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
            price_type VARCHAR(20) NOT NULL,
            quantity_min INTEGER NOT NULL,
            quantity_max INTEGER,
            price NUMERIC(10,2) NOT NULL,
            CONSTRAINT uq_variant_price_type_qty UNIQUE (variant_id, price_type, quantity_min)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_variant_prices_variant_id ON variant_prices(variant_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS product_sizes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            width NUMERIC(10,2) NOT NULL,
            height NUMERIC(10,2) NOT NULL,
            unit VARCHAR(10) NOT NULL DEFAULT 'in',
            label VARCHAR(100),
            CONSTRAINT uq_product_size_wh UNIQUE (product_id, width, height)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_sizes_product_id ON product_sizes(product_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS markup_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            scope VARCHAR(50) NOT NULL DEFAULT 'all',
            markup_pct NUMERIC(5,2) NOT NULL,
            min_margin NUMERIC(5,2),
            rounding VARCHAR(20) NOT NULL DEFAULT 'none',
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS product_push_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            ops_product_id VARCHAR(255),
            status VARCHAR(50) NOT NULL,
            error TEXT,
            pushed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sync_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
            supplier_name VARCHAR(255) NOT NULL,
            job_type VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            total_products INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            records_processed INTEGER NOT NULL DEFAULT 0,
            error_log TEXT,
            errors JSONB,
            discovery_mode VARCHAR(32)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sync_jobs_supplier_id ON sync_jobs(supplier_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS master_options (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ops_master_option_id INTEGER NOT NULL UNIQUE,
            title VARCHAR(255) NOT NULL,
            option_key VARCHAR(100),
            options_type VARCHAR(50),
            pricing_method VARCHAR(50),
            status INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            master_option_tag VARCHAR(100),
            raw_json JSONB,
            synced_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_master_options_ops_id ON master_options(ops_master_option_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS master_option_attributes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            master_option_id UUID NOT NULL REFERENCES master_options(id) ON DELETE CASCADE,
            ops_attribute_id INTEGER NOT NULL,
            title VARCHAR(255) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            default_price NUMERIC(10,2),
            raw_json JSONB,
            CONSTRAINT uq_master_option_attribute UNIQUE (master_option_id, ops_attribute_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_master_option_attributes_option_id ON master_option_attributes(master_option_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS push_mappings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_system VARCHAR(50) NOT NULL,
            source_product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            source_supplier_sku VARCHAR(255),
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            target_ops_base_url VARCHAR(500) NOT NULL,
            target_ops_product_id INTEGER NOT NULL,
            pushed_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            CONSTRAINT uq_push_mapping_product_customer UNIQUE (source_product_id, customer_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_push_mappings_product ON push_mappings(source_product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_push_mappings_customer ON push_mappings(customer_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS push_mapping_options (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            push_mapping_id UUID NOT NULL REFERENCES push_mappings(id) ON DELETE CASCADE,
            source_master_option_id INTEGER,
            source_master_attribute_id INTEGER,
            source_option_key VARCHAR(100),
            source_attribute_key VARCHAR(255),
            target_ops_option_id INTEGER,
            target_ops_attribute_id INTEGER,
            title VARCHAR(255),
            price NUMERIC(10,2),
            sort_order INTEGER,
            created_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_push_mapping_options_mapping ON push_mapping_options(push_mapping_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_product_decorations (
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            decoration_options JSONB NOT NULL DEFAULT '[]',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (customer_id, product_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_product_selections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            status VARCHAR(50) NOT NULL DEFAULT 'selected',
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            pushed_at TIMESTAMPTZ,
            CONSTRAINT uq_customer_product_selection UNIQUE (customer_id, product_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_product_selections_customer ON customer_product_selections(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_product_selections_product ON customer_product_selections(product_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS product_storefront_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            ops_category_id VARCHAR(100),
            option_mappings JSON NOT NULL DEFAULT '{}',
            pricing_overrides JSON NOT NULL DEFAULT '{}',
            CONSTRAINT uq_product_customer_config UNIQUE (product_id, customer_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_storefront_configs_product ON product_storefront_configs(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_storefront_configs_customer ON product_storefront_configs(customer_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) NOT NULL UNIQUE,
            hashed_password VARCHAR(255) NOT NULL,
            role VARCHAR(32) NOT NULL DEFAULT 'vg_admin',
            customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_customer_id ON users(customer_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_email VARCHAR(255),
            user_id VARCHAR(36),
            method VARCHAR(10) NOT NULL,
            path TEXT NOT NULL,
            status_code INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_email ON audit_logs(user_email)")


def downgrade() -> None:
    # Drop in reverse dependency order
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS product_storefront_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS customer_product_selections CASCADE")
    op.execute("DROP TABLE IF EXISTS customer_product_decorations CASCADE")
    op.execute("DROP TABLE IF EXISTS push_mapping_options CASCADE")
    op.execute("DROP TABLE IF EXISTS push_mappings CASCADE")
    op.execute("DROP TABLE IF EXISTS master_option_attributes CASCADE")
    op.execute("DROP TABLE IF EXISTS master_options CASCADE")
    op.execute("DROP TABLE IF EXISTS sync_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS product_push_log CASCADE")
    op.execute("DROP TABLE IF EXISTS markup_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS product_sizes CASCADE")
    op.execute("DROP TABLE IF EXISTS variant_prices CASCADE")
    op.execute("DROP TABLE IF EXISTS print_details CASCADE")
    op.execute("DROP TABLE IF EXISTS apparel_details CASCADE")
    op.execute("DROP TABLE IF EXISTS product_option_attributes CASCADE")
    op.execute("DROP TABLE IF EXISTS product_options CASCADE")
    op.execute("DROP TABLE IF EXISTS product_images CASCADE")
    op.execute("DROP TABLE IF EXISTS product_variants CASCADE")
    op.execute("DROP TABLE IF EXISTS products CASCADE")
    op.execute("DROP TABLE IF EXISTS categories CASCADE")
    op.execute("DROP TABLE IF EXISTS customers CASCADE")
    op.execute("DROP TABLE IF EXISTS suppliers CASCADE")
