# OnPrintShop Node

Custom n8n node for integrating with the OnPrintShop **GraphQL API**.

## Features

- **Query** customers, orders, products, statuses, quotes, stores, departments, batches
- **Mutate** orders/products/stocks and admin catalog entities (where enabled)

## Files

- `OnPrintShop.node.ts` - Main node implementation
- `onprintshop.svg` - Custom branded icon

## Credentials Required

Uses `OnPrintShopApi` credentials:
- **Client ID**: From OnPrintShop developer portal
- **Client Secret**: OAuth secret key
- **Base URL**: Your OPS API base URL
- **Token URL**: OAuth2 token endpoint

## API Documentation

https://documenter.getpostman.com/view/33263100/2sBXijHWys

## Usage Example

```
1. Add OnPrintShop node to workflow
2. Configure authentication
3. Select Resource + Operation (Query or Mutation)
4. Set parameters
5. Execute workflow
```

## Operations

- Queries: Customer/Order/Product/Status/Quote/Store/Department/etc.
- Mutations: Update Order Status, Set Shipment, Set Product catalog entities, Update Product Stock, etc.
- Some operations are marked Staging/Beta/Test in the Postman collection and may be disabled by OPS support on your instance.

