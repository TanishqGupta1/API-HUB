import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from modules.images.service import fetch_and_store_image, trigger_lazy_image_fetch
from modules.catalog.models import Product, ProductImage
from modules.suppliers.models import Supplier
from database import async_session

@pytest.mark.asyncio
async def test_fetch_and_store_image_mocked():
    """Test image download, checksum, and mocked S3 upload."""
    mock_image_data = b"fake-image-content"
    mock_url = "https://example.com/image.jpg"
    
    with patch("httpx.AsyncClient.get") as mock_get:
        # Mock successful download
        mock_response = MagicMock()
        mock_response.content = mock_image_data
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        cdn_url, checksum = await fetch_and_store_image(
            image_url=mock_url,
            supplier="sanmar",
            product_id="PC61",
            color="black",
            image_type="front",
            filename="pc61_black_front.jpg"
        )
        
        assert "cdn.example.com/sanmar/PC61/black/front/pc61_black_front.jpg" in cdn_url
        assert checksum is not None
        assert len(checksum) == 64 # SHA-256 hex length

@pytest.mark.asyncio
async def test_lazy_image_fetch_orchestration(seed_supplier: Supplier):
    """Test the full lazy pull flow from trigger to DB save."""
    async with async_session() as session:
        # 1. Create a product with no images
        product = Product(
            supplier_id=seed_supplier.id,
            supplier_sku="PC61",
            product_name="Test Product",
            product_type="apparel"
        )
        session.add(product)
        await session.commit()
        product_id = product.id

    # 2. Mock FTP and HTTPX to simulate finding and downloading 1 image
    with patch("modules.images.sanmar_ftp.SanMarFTPClient.list_images") as mock_list:
        mock_list.return_value = [{
            "filename": "PC61_Black_Front.jpg",
            "style": "PC61",
            "color": "Black",
            "type": "Front",
            "url": "ftp://mock/PC61_Black_Front.jpg"
        }]
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.content = b"content"
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp
            
            # 3. Trigger lazy fetch
            await trigger_lazy_image_fetch(product_id, seed_supplier.id)

    # 4. Verify DB state
    async with async_session() as session:
        from sqlalchemy import text
        imgs = (await session.execute(
            text("SELECT * FROM product_images WHERE product_id = :pid"), {"pid": product_id}
        )).fetchall()
        
        assert len(imgs) == 1
        assert imgs[0].color == "Black"
        assert imgs[0].image_type == "front"
        assert "cdn.example.com" in imgs[0].url
