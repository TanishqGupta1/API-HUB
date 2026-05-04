import asyncio
from database import async_session
from modules.suppliers.models import Supplier
from sqlalchemy import select, delete

async def clean():
    allowed_names = ['Visual Graphics OPS', '4over', 'S&S Activewear', 'SanMar']
    async with async_session() as s:
        # Find supplier IDs that need to be deleted
        res = await s.execute(select(Supplier.id).where(Supplier.name.not_in(allowed_names)))
        ids = res.scalars().all()
        
        if not ids:
            print('No duplicate suppliers found')
            return

        print(f"Deleting dependencies for {len(ids)} suppliers...")
        
        from modules.catalog.models import Product, Category, CustomerProductSelection
        from modules.sync_jobs.models import SyncJob
        
        # We need to manually delete things that reference the products first, 
        # but let's see if we can just delete from the dependent tables.
        # Actually, let's just delete products and categories first
        
        await s.execute(delete(Category).where(Category.supplier_id.in_(ids)))
        await s.execute(delete(SyncJob).where(SyncJob.supplier_id.in_(ids)))
        
        # Deleting products might require deleting variants, images, etc.
        # If the DB has ON DELETE CASCADE it's fine, otherwise we need to query products and delete them.
        from sqlalchemy import text
        await s.execute(text("DELETE FROM push_mappings WHERE source_product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids))"), {"ids": ids})
        await s.execute(text("DELETE FROM customer_product_selections WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids))"), {"ids": ids})
        await s.execute(text("DELETE FROM product_option_attributes WHERE product_option_id IN (SELECT id FROM product_options WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids)))"), {"ids": ids})
        await s.execute(text("DELETE FROM product_options WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids))"), {"ids": ids})
        await s.execute(text("DELETE FROM variant_prices WHERE variant_id IN (SELECT id FROM product_variants WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids)))"), {"ids": ids})
        await s.execute(text("DELETE FROM product_variants WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids))"), {"ids": ids})
        await s.execute(text("DELETE FROM product_images WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids))"), {"ids": ids})
        await s.execute(text("DELETE FROM product_apparel_details WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids))"), {"ids": ids})
        await s.execute(text("DELETE FROM product_print_details WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids))"), {"ids": ids})
        await s.execute(text("DELETE FROM product_sizes WHERE product_id IN (SELECT id FROM products WHERE supplier_id = ANY(:ids))"), {"ids": ids})
        
        await s.execute(delete(Product).where(Product.supplier_id.in_(ids)))
        
        await s.execute(delete(Supplier).where(Supplier.id.in_(ids)))
        await s.commit()
    print('Cleaned up duplicate suppliers')
    asyncio.run(clean())
