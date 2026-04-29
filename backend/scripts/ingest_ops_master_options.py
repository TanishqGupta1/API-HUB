import asyncio
import json
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

INGEST_SECRET = os.getenv("INGEST_SHARED_SECRET", "vg-hub-ingest-secret-2026")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def transform_ops_data(raw_data):
    batch = []
    for item in raw_data:
        # OPS often returns meta fields like _operation and _total inside the list if it's a specific response format
        # but here it looks like a list of objects.
        if not isinstance(item, dict) or "master_option_id" not in item:
            continue
            
        attributes = []
        for attr in item.get("attributes", []):
            attributes.append({
                "ops_attribute_id": int(attr["master_attribute_id"]),
                "title": attr.get("label") or attr.get("title") or "Unnamed Attribute",
                "sort_order": int(attr.get("sort_order", 0)),
                "default_price": float(attr.get("setup_cost", 0)),
                "raw_json": attr
            })
            
        batch.append({
            "ops_master_option_id": int(item["master_option_id"]),
            "title": item["title"],
            "option_key": item.get("option_key"),
            "options_type": item.get("options_type"),
            "pricing_method": item.get("pricing_method"),
            "status": int(item.get("status", 1)),
            "sort_order": int(item.get("sort_order", 0)),
            "description": item.get("description"),
            "attributes": attributes,
            "raw_json": item
        })
    return batch

async def main():
    # The JSON data provided by the user (truncated in the prompt, so we assume it's in a file or we would have it)
    # For this exercise, I will assume the user wants me to process the data they JUST sent.
    # Since I cannot read the "last message" as a file, I will expect a file named 'ops_data.json' in the same dir.
    
    data_path = Path(__file__).parent / "ops_data.json"
    if not data_path.exists():
        print(f"Error: {data_path} not found. Please save the OPS JSON to this location.")
        return

    with open(data_path, "r") as f:
        raw_data = json.load(f)

    batch = transform_ops_data(raw_data)
    print(f"Transformed {len(batch)} master options. Sending to Hub...")

    async with httpx.AsyncClient() as client:
        url = f"{API_BASE_URL}/api/ingest/master-options"
        headers = {"X-Ingest-Secret": INGEST_SECRET}
        
        response = await client.post(url, json=batch, headers=headers, timeout=30.0)
        
        if response.status_code == 200:
            print("Success!")
            print(response.json())
        else:
            print(f"Failed with status {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(main())
