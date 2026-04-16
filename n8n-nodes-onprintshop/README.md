# n8n-nodes-onprintshop

This is an n8n community node for OnPrintShop integration.

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

### Order Management
- **List Orders**: Get all orders
- **Get Order**: Retrieve order details
- **Create Order**: Place new order
- **Update Order**: Modify order information
- **Delete Order**: Cancel/remove order
- **Get Order Status**: Check order status

### Product Management
- **List Products**: Get product catalog
- **Get Product**: Retrieve product details
- **Create Product**: Add new product
- **Update Product**: Modify product information
- **Delete Product**: Remove product

### Customer Management
- **List Customers**: Get all customers
- **Get Customer**: Retrieve customer details
- **Create Customer**: Add new customer
- **Update Customer**: Modify customer information
- **Delete Customer**: Remove customer

### Inventory Management
- **Check Stock**: Get inventory levels
- **Update Stock**: Modify stock quantities
- **Get Product Availability**: Check if products are in stock

## Credentials

You need an OnPrintShop API key.

Get it from:
1. Log into your OnPrintShop admin panel
2. Go to **Settings > API**
3. Generate API key

Required fields:
- **API Key**: Your OnPrintShop API key
- **Shop URL**: Your shop domain (e.g., yourshop.onprintshop.com)

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
- [OnPrintShop Documentation](https://www.onprintshop.com/)
- [GitHub Repository](https://github.com/cderamos-2ct/n8n-nodes-onprintshop)

## Version History

### 1.0.0
- Initial release
- Full API coverage
- Order, product, customer, and inventory management

## License

[MIT](LICENSE)

## Author

Created by cderamos-2ct

