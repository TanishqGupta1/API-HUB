import asyncio
from sqlalchemy import text
from database import async_session

async def main():
    async with async_session() as db:
        # Define target customer names to remove
        target_customer_names = [
            "Test Storefront",
            "Task7 Co",
            "Test Customer"
        ]
        
        # Build list for SQL IN clause
        names_str = "', '".join(target_customer_names)
        
        # Delete dependencies for customers
        await db.execute(text(f"DELETE FROM push_mappings WHERE customer_id IN (SELECT id FROM customers WHERE name IN ('{names_str}') OR name LIKE 'Test Storefront%' OR name LIKE 'Task7 Co%');"))
        await db.execute(text(f"DELETE FROM product_push_log WHERE customer_id IN (SELECT id FROM customers WHERE name IN ('{names_str}') OR name LIKE 'Test Storefront%' OR name LIKE 'Task7 Co%');"))
        await db.execute(text(f"DELETE FROM customer_product_decorations WHERE customer_id IN (SELECT id FROM customers WHERE name IN ('{names_str}') OR name LIKE 'Test Storefront%' OR name LIKE 'Task7 Co%');"))
        
        # Finally delete customers
        await db.execute(text(f"DELETE FROM customers WHERE name IN ('{names_str}') OR name LIKE 'Test Storefront%' OR name LIKE 'Task7 Co%';"))
        
        await db.commit()
        print("Additional dummy storefronts successfully deleted!")

if __name__ == "__main__":
    asyncio.run(main())
