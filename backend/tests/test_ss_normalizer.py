import pytest
from modules.rest_connector.ss_normalizer import ss_to_ps_format

def test_ss_to_ps_format_grouping():
    sample_data = [
        {
            "sku": "SKU1",
            "yourPrice": 10.0,
            "styleID": "S1",
            "styleName": "Product 1",
            "qty": 100,
        },
        {
            "sku": "SKU2",
            "yourPrice": 10.0,
            "styleID": "S1",
            "styleName": "Product 1",
            "qty": 50,
        }
    ]
    
    prods, invs, prcs, meds = ss_to_ps_format(sample_data)
    
    assert len(prods) == 1
    assert prods[0].product_id == "S1"
    assert len(prods[0].parts) == 2
    assert len(invs) == 2
    assert len(prcs) == 2

def test_ss_to_ps_format_skips_malformed():
    sample_data = [
        {"sku": "SKU1"}, # No styleID
        {"styleID": "S1"}, # No sku
        {"sku": "SKU3", "styleID": "S1", "qty": 10} # Valid
    ]
    
    prods, invs, prcs, meds = ss_to_ps_format(sample_data)
    
    assert len(prods) == 1
    assert len(invs) == 1
    assert invs[0].part_id == "SKU3"

def test_ss_to_ps_format_media_deduplication():
    sample_data = [
        {
            "sku": "SKU1",
            "styleID": "S1",
            "colorName": "Red",
            "colorFrontImage": "http://img.com/1"
        },
        {
            "sku": "SKU2",
            "styleID": "S1",
            "colorName": "Red",
            "colorFrontImage": "http://img.com/1"
        },
        {
            "sku": "SKU3",
            "styleID": "S1",
            "colorName": "Blue",
            "colorFrontImage": "http://img.com/2"
        }
    ]
    
    prods, invs, prcs, meds = ss_to_ps_format(sample_data)
    
    # 2 Red (identical) + 1 Blue = 2 unique media items
    assert len(meds) == 2
    colors = [m.color_name for m in meds]
    assert "Red" in colors
    assert "Blue" in colors
