from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import httpx
from PIL import Image

if TYPE_CHECKING:
    from modules.decorations.schemas import DecorationOption

log = logging.getLogger(__name__)

async def generate_decorated_image(
    base_image_url: str,
    options: list[DecorationOption],
) -> bytes:
    """
    Apply one or more decorations (logos/text) onto a base product image.
    Returns the resulting image as bytes (PNG).
    """
    try:
        # 1. Fetch base image
        async with httpx.AsyncClient() as client:
            resp = await client.get(base_image_url, timeout=30.0)
            resp.raise_for_status()
            base_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")

        # 2. Apply each decoration
        canvas = base_img.copy()
        base_w, base_h = canvas.size

        for opt in options:
            if opt.type == "logo" and opt.url:
                # Fetch logo
                async with httpx.AsyncClient() as client:
                    lresp = await client.get(opt.url, timeout=10.0)
                    lresp.raise_for_status()
                    logo_img = Image.open(io.BytesIO(lresp.content)).convert("RGBA")

                # Scale logo
                # 'opt.scale' is a multiplier (0.1 to 2.0)
                # We assume the logo should be roughly 15% of product width at scale=1.0
                target_w = int(base_w * 0.15 * opt.scale)
                logo_aspect = logo_img.height / logo_img.width
                target_h = int(target_w * logo_aspect)
                
                logo_resized = logo_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

                # Position
                # opt.position_x/y are percentages (0-100)
                x = int(base_w * (opt.position_x / 100)) - (target_w // 2)
                y = int(base_h * (opt.position_y / 100)) - (target_h // 2)

                # Rotate if needed
                if opt.rotation:
                    logo_resized = logo_resized.rotate(-opt.rotation, expand=True)

                # Paste with alpha mask
                canvas.alpha_composite(logo_resized, (x, y))

        # 3. Export
        out_buf = io.BytesIO()
        canvas.save(out_buf, format="PNG")
        return out_buf.getvalue()

    except Exception as e:
        log.error(f"Image decoration failed: {e}")
        raise
