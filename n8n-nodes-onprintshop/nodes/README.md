# OnPrintShop Node

Custom n8n node for integrating with OnPrintShop printing services API.

## Features

- **Submit Print Jobs**: Upload and submit files for printing
- **Track Orders**: Monitor order status and progress
- **Product Catalog**: Manage printing products and options
- **Payment Processing**: Handle payment workflows
- **Customer Management**: Manage customer accounts

## Files

- `OnPrintShop.node.ts` - Main node implementation (6,799 lines)
- `onprintshop.svg` - Custom branded icon

## Credentials Required

Uses `OnPrintShopApi` credentials:
- **Client ID**: From OnPrintShop developer portal
- **Client Secret**: OAuth secret key
- **Environment**: Production or Sandbox

## API Documentation

https://documenter.getpostman.com/view/33263100/2sA3kVmMgH

## Usage Example

```
1. Add OnPrintShop node to workflow
2. Configure authentication
3. Select operation (Submit Job, Track Order, etc.)
4. Set parameters
5. Execute workflow
```

## Operations

- Submit Print Job
- Check Order Status
- List Products
- Process Payment
- Manage Customer Accounts
- Upload Files


