# SanMar Hybrid Integration Strategy (FTP + PromoStandards)

**Goal:** implement a robust, high-performance SanMar integration by combining bulk SFTP data with real-time API checks.

## 1. Bulk Inbound Pipeline (SFTP)
*   **File:** `SanMar_EPDD.csv`
*   **Frequency:** Daily (6 AM PST)
*   **Purpose:** Initial catalog load, product descriptions, brand mapping, and model images.
*   **Implementation:** n8n workflow `sanmar-sftp-pull.json` (First 100 products initially).

## 2. Real-Time Data (PromoStandards SOAP)
*   **Services:** `Inventory v2.0.0`, `Product Data v2.0.0`, `Media Content v1.1.0`.
*   **Purpose:** 
    *   **Live Stock:** Fetch exact quantities per warehouse during the checkout flow.
    *   **High-Res Media:** Pull all model angles and spec sheets on-demand for the PDP.
    *   **Pricing:** Verify customer-specific pricing tiers.
*   **Implementation:** 
    *   Extend `backend/modules/promostandards` to support SanMar WSDLs.
    *   Add a "Live Check" button/trigger in the storefront.

## 3. Environment Config (`.env`)
Ensure the following are populated for both FTP and SOAP:
```bash
# FTP (Bulk)
SANMAR_SFTP_USER=
SANMAR_SFTP_PASS=

# Web Services (Real-time)
SANMAR_WS_USER=
SANMAR_WS_PASS=
SANMAR_WS_CUST_NUM=
```

## 4. Next Steps
1.  **Import SFTP Workflow:** Load `sanmar-sftp-pull.json` into n8n and verify the first 100 products.
2.  **WSDL Integration:** Start mapping the SanMar Inventory WSDL in the backend to enable live stock lookups.
