"""
Download product images from supplier CDN and upload into OPS's managed S3 path.

OPS stores gallery images at:
  s3://ctmediaimg/ctmediaon_staging/images/products_gallery_images/{name}.jpg
  s3://ctmediaimg/ctmediaon_staging/images/products_gallery_images/{name}_thumb.jpg

We upload both so OPS can serve them directly via bare filename (no optimizeimg needed).
Also updates product_images.ops_filename in our DB so the gateway uses the bare name.

Usage:
    python /app/scripts/sync_images_to_s3.py --sku L420
    python /app/scripts/sync_images_to_s3.py --sku L420 --dry-run
"""
import argparse, asyncio, hashlib, io, mimetypes, os, sys
from pathlib import Path, PurePosixPath
import httpx
import boto3
from PIL import Image
from dotenv import load_dotenv

# Support running from repo root or backend/ dir
_here = Path(__file__).resolve()
for _candidate in (_here.parent.parent.parent / ".env", _here.parent.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break

sys.path.insert(0, str(_here.parent.parent))

S3_BUCKET    = os.environ.get("S3_PRODUCT_IMAGES_BUCKET", "ctmediaimg")
S3_REGION    = os.environ.get("S3_REGION", "us-west-1")
AWS_KEY      = os.environ.get("S3_ACCESS_KEY_ID")
AWS_SECRET   = os.environ.get("S3_SECRET_ACCESS_KEY")

OPS_GALLERY_PREFIX = "ctmediaon_staging/images/products_gallery_images"
THUMB_SIZE = (300, 300)  # OPS thumbnail max dimension
SKIP_EXTENSIONS = {".gif"}


def _ops_filename(supplier_sku: str, source_url: str) -> str:
    """Stable bare filename for OPS gallery (no path prefix)."""
    fname = PurePosixPath(source_url.split("?")[0]).name
    ext = PurePosixPath(fname).suffix.lower()
    stem = PurePosixPath(fname).stem
    url_hash = hashlib.md5(source_url.encode()).hexdigest()[:6]
    return f"{supplier_sku}_{stem}_{url_hash}{ext}"


def _make_thumb(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail(THUMB_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _upload(s3_client, key: str, data: bytes) -> None:
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ContentType="image/jpeg",
    )
    s3_client.put_object_acl(Bucket=S3_BUCKET, Key=key, ACL="public-read")


async def _download(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        r = await client.get(url, follow_redirects=True, timeout=20)
        if r.status_code == 200:
            return r.content
        print(f"  SKIP {r.status_code} {url}")
        return None
    except Exception as e:
        print(f"  ERR download {url}: {e}")
        return None


async def main(sku: str, dry_run: bool) -> None:
    from database import async_session
    from sqlalchemy import text

    s3 = boto3.client(
        "s3",
        region_name=S3_REGION,
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET,
    )

    async with async_session() as db:
        r = await db.execute(text(
            "SELECT pi.id, pi.url, pi.image_type, pi.sort_order "
            "FROM product_images pi JOIN products p ON pi.product_id=p.id "
            "WHERE p.supplier_sku=:sku ORDER BY "
            "CASE pi.image_type WHEN 'primary' THEN 0 WHEN 'front' THEN 1 ELSE 2 END, "
            "pi.sort_order"
        ), {"sku": sku})
        images = r.fetchall()

    skip = [i for i in images if any(i.url.lower().endswith(e) for e in SKIP_EXTENSIONS)]
    todo = [i for i in images if i not in skip and i.url]
    print(f"Found {len(images)} images for {sku}: {len(todo)} to upload, {len(skip)} GIFs skipped")

    # The primary image (first front/primary) also goes to product/ path
    # for imagename + product_desc_image in setProduct.
    primary_img = next(
        (i for i in todo if i.image_type in ("primary", "front")), None
    )

    uploaded = 0
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as http:
        for img in todo:
            url = img.url
            ext = PurePosixPath(url.split("?")[0]).suffix.lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                print(f"  SKIP unknown ext: {url}")
                continue

            ops_name = _ops_filename(sku, url)
            ops_name_jpg = PurePosixPath(ops_name).stem + ".jpg"
            main_key  = f"{OPS_GALLERY_PREFIX}/{ops_name_jpg}"
            thumb_key = f"{OPS_GALLERY_PREFIX}/{PurePosixPath(ops_name_jpg).stem}_thumb.jpg"

            print(f"  [{img.image_type}] {PurePosixPath(url).name}")
            print(f"         ops: {ops_name_jpg}")

            if dry_run:
                print(f"         DRY RUN")
                continue

            data = await _download(http, url)
            if data is None:
                continue

            try:
                thumb_data = _make_thumb(data)
                _upload(s3, main_key, data)
                _upload(s3, thumb_key, thumb_data)
                print(f"         OK {len(data)//1024}KB + {len(thumb_data)//1024}KB thumb")
            except Exception as e:
                print(f"         ERR: {e}")
                continue

            # Store bare ops_filename in DB so gateway uses it instead of URL
            async with async_session() as db:
                await db.execute(
                    text("UPDATE product_images SET ops_filename=:name WHERE id=:id"),
                    {"name": ops_name_jpg, "id": str(img.id)},
                )
                await db.commit()

            # Also copy primary image to product/ path for imagename + product_desc_image
            if img is primary_img:
                product_key = f"ctmediaon_staging/images/product/{ops_name_jpg}"
                _upload(s3, product_key, data)
                print(f"         OK also uploaded to product/ path for setProduct imagename")

            uploaded += 1

    print(f"\nDone. {uploaded} images uploaded to OPS S3 gallery path.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.sku, args.dry_run))
