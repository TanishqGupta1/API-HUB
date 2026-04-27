from zeep import Client, Settings
from zeep.transports import Transport
import httpx

url = 'https://services.alphabroder.com/productData2/wsdl/ProductDataService.wsdl'
settings = Settings(strict=False)
transport = Transport(timeout=10)

print(f"Testing URL: {url}")
try:
    client = Client(url, settings=settings, transport=transport)
    print("Client initialized")
    svc = client.service
    print("Service accessed")
except Exception as e:
    print(f"Failed: {type(e).__name__}: {e}")

url_wsdl = url + "?wsdl"
print(f"\nTesting URL: {url_wsdl}")
try:
    # Use httpx to follow redirects manually if needed, or trust zeep's transport
    client = Client(url_wsdl, settings=settings, transport=transport)
    print("Client initialized")
    svc = client.service
    print("Service accessed")
    print("Operations:", dir(svc))
except Exception as e:
    print(f"Failed: {type(e).__name__}: {e}")
