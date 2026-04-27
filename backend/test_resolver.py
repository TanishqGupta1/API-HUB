import json
from modules.promostandards.resolver import resolve_wsdl_url

endpoints = json.loads('[{"URL": "https://services.alphabroder.com/productData2/wsdl/ProductDataService.wsdl", "Service": {"WSDL": "https://promostandards.org/wp-content/uploads/2025/07/ProductData2-0-0-1.zip", "Status": "Production", "Version": "2.0.0", "ServiceType": {"Code": "Product", "Name": "Product Data"}}, "TestURL": "https://devservices.alphabroder.com/productData2/wsdl/ProductDataService.wsdl"}]')

res = resolve_wsdl_url(endpoints, "product_data")
print(f"Result: {res}")
