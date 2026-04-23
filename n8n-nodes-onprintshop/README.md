# n8n-nodes-onprintshop

This is an n8n community node for the **OnPrintShop GraphQL API**.

[n8n](https://n8n.io/) is a [fair-code licensed](https://docs.n8n.io/reference/license/) workflow automation platform.

[Installation](#installation) | [Operations](#operations) | [Credentials](#credentials) | [Compatibility](#compatibility) | [Resources](#resources)

## Installation

Follow the [installation guide](https://docs.n8n.io/integrations/community-nodes/installation/) in the n8n community nodes documentation.

### Community Nodes (Recommended)

1. Go to **Settings > Community Nodes**
2. Select **Install a community node**
3. Enter `n8n-nodes-onprintshop`
4. Click **Install**
5. Restart n8n

### Manual Installation

```bash
npm install n8n-nodes-onprintshop
```

## Operations

The node groups operations by **Resource**.

### Queries (Read)
- **Customer**: Get / Get Many, plus **Get User Basket (Test)**
- **Customer Address**: Get Many
- **Order**: Get / Get Many, **Get Shipments**
- **Order Details**: Get Many
- **Order Shipment**: Get Many (with pagination helpers)
- **Ship To Multiple**: Get Many (by `order_id`, per OPS query contract)
- **Product**: Get Simple/Detailed (single/many), master options/rules/prices, categories, FAQs, stocks, plus catalog helpers (tags/groups/formulas/ranges)
- **Product Stocks**: Get Many (with pagination helpers)
- **Status**: Get / Get Many
- **Batch**: Get Many
- **Quote**: Get Many
- **Quote Product**: Get Many
- **Store**: Store details + countries + markup + payment terms + store address (+ staging summaries)
- **Department**: Get Many

### Mutations (Write)
- **Operational**: Update Order Status, Set Order Product, Set Batch, Set Shipment
- **Catalog/Admin**: Set Product / Price / Size / Category, Set Product Pages, Assign Options, Set Product Option Rules, Set Option Group, Set Custom Formula, Set Master Option + related (tags/attributes/ranges/prices)
- **Customer/Admin**: Set Customer, Notify User, Set Customer Address (Staging)
- **Store/Admin**: Set Store Address, Set Department, Set Store, Set Store Markup
- **Quote/Order (Staging/Beta/Test)**: Set Quote, Set Order (Staging), Modify Order Product (Beta), Set User Basket (Test), plus additional-option beta mutations
- **Inventory**: Update Product Stock

> Note: Operations marked **Staging/Beta/Test** exist in the official Postman collection but may be disabled on your OPS instance.

## Credentials

You need OnPrintShop OAuth2 credentials.

Get it from:
1. Log into your OnPrintShop admin panel
2. Go to **Settings > API**
3. Create an OAuth client (Client ID + Client Secret)

Required fields:
- **Client ID**: OAuth2 Client ID
- **Client Secret**: OAuth2 Client Secret
- **Base URL**: Your OPS API base URL (used for GraphQL at `{{baseUrl}}/api/`)
- **Token URL**: OAuth2 token endpoint (defaults to `https://api.onprintshop.com/oauth/token`)

## Compatibility

Tested with:
- n8n v1.0.0+
- Node.js 18+

## Usage Example

### Creating an Order

1. Add **OnPrintShop** node to workflow
2. Select **Resource**: Order
3. Select **Operation**: Create Order
4. Fill in order details
5. Execute workflow

## Resources

- [n8n community nodes documentation](https://docs.n8n.io/integrations/community-nodes/)
- OnPrintShop Postman docs: https://documenter.getpostman.com/view/33263100/2sBXijHWys
- [GitHub Repository](https://github.com/cderamos-2ct/n8n-nodes-onprintshop)

## Version History

### 1.0.0
- Initial release
- Synced to the official Postman collection (2026-04-23)

## License

[MIT](LICENSE)

## Author

Created by cderamos-2ct
