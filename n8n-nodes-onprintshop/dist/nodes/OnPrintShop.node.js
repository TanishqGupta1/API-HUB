"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OnPrintShop = void 0;
const n8n_workflow_1 = require("n8n-workflow");
function stripTrailingSlashes(url) {
    return url.replace(/\/+$/, '');
}
class OnPrintShop {
    constructor() {
        this.description = {
            displayName: 'OnPrintShop',
            name: 'onPrintShop',
            icon: 'file:onprintshop.svg',
            group: ['transform'],
            version: 1,
            subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
            description: 'Interact with OnPrintShop API',
            defaults: {
                name: 'OnPrintShop',
            },
            inputs: ['main'],
            outputs: ['main'],
            credentials: [
                {
                    name: 'onPrintShopApi',
                    required: true,
                },
            ],
            properties: [
                // Global safety toggle for large queries
                {
                    displayName: 'Safe Mode',
                    name: 'safeMode',
                    description: 'If enabled, retries first page without nested groups when server returns 5xx',
                    type: 'boolean',
                    default: false,
                },
                {
                    displayName: 'Resource',
                    name: 'resource',
                    type: 'options',
                    noDataExpression: true,
                    options: [
                        {
                            name: 'Customer',
                            value: 'customer',
                        },
                        {
                            name: 'Order',
                            value: 'order',
                        },
                        {
                            name: 'Product',
                            value: 'product',
                        },
                        {
                            name: 'Status',
                            value: 'status',
                        },
                        {
                            name: 'Customer Address',
                            value: 'customerAddress',
                        },
                        {
                            name: 'Order Details',
                            value: 'orderDetails',
                        },
                        {
                            name: 'Order Shipment',
                            value: 'orderShipment',
                        },
                        {
                            name: 'Ship To Multiple',
                            value: 'shipToMultipleAddress',
                        },
                        {
                            name: 'Product Stocks',
                            value: 'productStocks',
                        },
                        {
                            name: 'Batch',
                            value: 'batch',
                        },
                        {
                            name: 'Department',
                            value: 'department',
                        },
                        {
                            name: 'Mutation',
                            value: 'mutation',
                        },
                        {
                            name: 'Quote',
                            value: 'quote',
                        },
                        {
                            name: 'Quote Product',
                            value: 'quoteProduct',
                        },
                        {
                            name: 'Store',
                            value: 'store',
                        },
                    ],
                    default: 'customer',
                },
                // Customer Address Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['customerAddress'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many customer addresses' }],
                    default: 'getAll',
                },
                // Customer Address: User ID (Required)
                {
                    displayName: 'User ID',
                    name: 'userId',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['customerAddress'], operation: ['getAll'] } },
                    default: '',
                    description: 'Customer/User ID to fetch addresses for (required)',
                },
                // Customer Address: Fields
                {
                    displayName: 'Address Fields',
                    name: 'addressFieldsCustomer',
                    type: 'multiOptions',
                    displayOptions: { show: { resource: ['customerAddress'], operation: ['getAll'] } },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Address Type', value: 'address_type' },
                        { name: 'City', value: 'city' },
                        { name: 'Company', value: 'company' },
                        { name: 'Country', value: 'country' },
                        { name: 'Extrafield', value: 'extrafield' },
                        { name: 'First Name', value: 'first_name' },
                        { name: 'Is Default Address', value: 'is_default_address' },
                        { name: 'Last Name', value: 'last_name' },
                        { name: 'Name', value: 'name' },
                        { name: 'Postcode', value: 'postcode' },
                        { name: 'State', value: 'state' },
                        { name: 'State Code', value: 'state_code' },
                        { name: 'Street Address', value: 'street_address' },
                        { name: 'Suburb', value: 'suburb' },
                        { name: 'Telephone', value: 'telephone' },
                    ],
                    default: [
                        'name',
                        'first_name',
                        'last_name',
                        'company',
                        'street_address',
                        'city',
                        'state',
                        'country',
                        'telephone',
                        'address_type',
                        'is_default_address',
                    ],
                },
                // Order Details Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['orderDetails'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many order details' }],
                    default: 'getAll',
                },
                // Order Details: Query Parameters & Fields (reuse Order query params and product fields getAll)
                {
                    displayName: 'Query Parameters',
                    name: 'queryParameters',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    displayOptions: { show: { resource: ['orderDetails'], operation: ['getAll'] } },
                    default: {},
                    options: [
                        { displayName: 'Orders ID', name: 'orders_id', type: 'number', default: 0 },
                        { displayName: 'Orders Products ID', name: 'orders_products_id', type: 'number', default: 0 },
                        { displayName: 'Order Product Status', name: 'order_product_status', type: 'number', default: 0 },
                        { displayName: 'Store ID', name: 'store_id', type: 'string', default: '' },
                        { displayName: 'From Date', name: 'from_date', type: 'dateTime', default: '' },
                        { displayName: 'To Date', name: 'to_date', type: 'dateTime', default: '' },
                        { displayName: 'Order Status', name: 'order_status', type: 'string', default: '' },
                        { displayName: 'Customer ID', name: 'customer_id', type: 'number', default: 0 },
                        { displayName: 'Order Type', name: 'order_type', type: 'options', options: [{ name: 'All', value: '' }, { name: 'Standard', value: 'STANDARD' }, { name: 'Quote', value: 'QUOTE' }], default: '' },
                        { displayName: 'Page Size', name: 'pageSize', type: 'number', typeOptions: { minValue: 1, maxValue: 250 }, default: 250 },
                        { displayName: 'Page Delay (ms)', name: 'pageDelay', type: 'number', typeOptions: { minValue: 25, maxValue: 1000 }, default: 50 },
                    ],
                },
                // Order Details: Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPages',
                    type: 'boolean',
                    default: false,
                    displayOptions: { show: { resource: ['orderDetails'], operation: ['getAll'] } },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)'
                },
                {
                    displayName: 'Product Fields',
                    name: 'productFieldsOrderDetails',
                    type: 'multiOptions',
                    displayOptions: { show: { resource: ['orderDetails'], operation: ['getAll'] } },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Orders Products ID', value: 'orders_products_id' },
                        { name: 'Product Size Details', value: 'product_size_details' },
                        { name: 'Products Name', value: 'products_name' },
                        { name: 'Products Title', value: 'products_title' },
                        { name: 'Products SKU', value: 'products_sku' },
                        { name: 'Products Price', value: 'products_price' },
                        { name: 'Products Quantity', value: 'products_quantity' },
                        { name: 'Product Status', value: 'product_status' },
                    ],
                    default: ['orders_products_id', 'products_name', 'products_sku', 'products_price', 'products_quantity', 'product_status'],
                },
                // Order Shipment Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['orderShipment'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many order shipments' }],
                    default: 'getAll',
                },
                // Order Shipment: Query Parameters & Fields (reuse Order params and shipment_detail fields)
                {
                    displayName: 'Query Parameters',
                    name: 'queryParameters',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    displayOptions: { show: { resource: ['orderShipment'], operation: ['getAll'] } },
                    default: {},
                    options: [
                        { displayName: 'Orders ID', name: 'orders_id', type: 'number', default: 0 },
                        { displayName: 'From Date', name: 'from_date', type: 'dateTime', default: '' },
                        { displayName: 'To Date', name: 'to_date', type: 'dateTime', default: '' },
                        { displayName: 'Order Status', name: 'order_status', type: 'string', default: '' },
                        { displayName: 'Customer ID', name: 'customer_id', type: 'number', default: 0 },
                        { displayName: 'Order Type', name: 'order_type', type: 'options', options: [{ name: 'All', value: '' }, { name: 'Standard', value: 'STANDARD' }, { name: 'Quote', value: 'QUOTE' }], default: '' },
                        { displayName: 'Page Size', name: 'pageSize', type: 'number', typeOptions: { minValue: 1, maxValue: 250 }, default: 250 },
                        { displayName: 'Page Delay (ms)', name: 'pageDelay', type: 'number', typeOptions: { minValue: 25, maxValue: 1000 }, default: 50 },
                    ],
                },
                // Order Shipment: Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPages',
                    type: 'boolean',
                    default: false,
                    displayOptions: { show: { resource: ['orderShipment'], operation: ['getAll'] } },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)'
                },
                {
                    displayName: 'Shipment Fields',
                    name: 'shipmentFieldsOrderShipment',
                    type: 'multiOptions',
                    displayOptions: { show: { resource: ['orderShipment'], operation: ['getAll'] } },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Shipment Shipping Type ID', value: 'shipment_shipping_type_id' },
                        { name: 'Shipment Tracking Number', value: 'shipment_tracking_number' },
                        { name: 'Shipment Company', value: 'shipment_company' },
                        { name: 'Shipment Total Weight', value: 'shipment_total_weight' },
                        { name: 'Shipment Package', value: 'shipment_package' },
                    ],
                    default: ['shipment_tracking_number', 'shipment_company', 'shipment_total_weight'],
                },
                // Ship To Multiple Ops
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['shipToMultipleAddress'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many ship-to-multiple addresses' }],
                    default: 'getAll',
                },
                {
                    displayName: 'Order ID',
                    name: 'shipToMultiple_order_id',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['shipToMultipleAddress'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Order ID to fetch ship-to-multiple addresses for',
                },
                {
                    displayName: 'Fields',
                    name: 'stmFields',
                    type: 'multiOptions',
                    displayOptions: { show: { resource: ['shipToMultipleAddress'], operation: ['getAll'] } },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Shipping Type ID', value: 'ship_to_multiple_address_shipping_type_id' },
                        { name: 'Shipping Price', value: 'ship_to_multiple_address_shipping_price' },
                        { name: 'Shipping Name', value: 'ship_to_multiple_address_shipping_name' },
                        { name: 'Shipping Mode', value: 'ship_to_multiple_address_shipping_mode' },
                        { name: 'Production Due Date', value: 'ship_to_multiple_address_production_due_date' },
                        { name: 'Shipment Due Date', value: 'ship_to_multiple_address_shipment_due_date' },
                        { name: 'Product Details', value: 'ship_to_multiple_address_product_details' },
                        { name: 'Delivery Name', value: 'ship_to_multiple_address_delivery_name' },
                        { name: 'Delivery Company', value: 'ship_to_multiple_address_delivery_company' },
                        { name: 'Delivery Street Address', value: 'ship_to_multiple_address_delivery_street_address' },
                        { name: 'Delivery Suburb', value: 'ship_to_multiple_address_delivery_suburb' },
                        { name: 'Delivery City', value: 'ship_to_multiple_address_delivery_city' },
                        { name: 'Delivery Postcode', value: 'ship_to_multiple_address_delivery_postcode' },
                        { name: 'Delivery State', value: 'ship_to_multiple_address_delivery_state' },
                        { name: 'Delivery Country', value: 'ship_to_multiple_address_delivery_country' },
                        { name: 'Delivery Telephone', value: 'ship_to_multiple_address_delivery_telephone' },
                        { name: 'Blind Address', value: 'ship_to_multiple_address_blind_address' },
                        { name: 'Extra Field', value: 'ship_to_multiple_address_extra_field' },
                    ],
                    default: [
                        'ship_to_multiple_address_shipping_type_id',
                        'ship_to_multiple_address_shipping_price',
                        'ship_to_multiple_address_shipping_name',
                        'ship_to_multiple_address_shipping_mode',
                        'ship_to_multiple_address_production_due_date',
                        'ship_to_multiple_address_shipment_due_date',
                        'ship_to_multiple_address_product_details',
                        'ship_to_multiple_address_delivery_name',
                        'ship_to_multiple_address_delivery_company',
                        'ship_to_multiple_address_delivery_street_address',
                        'ship_to_multiple_address_delivery_suburb',
                        'ship_to_multiple_address_delivery_city',
                        'ship_to_multiple_address_delivery_postcode',
                        'ship_to_multiple_address_delivery_state',
                        'ship_to_multiple_address_delivery_country',
                        'ship_to_multiple_address_delivery_telephone',
                        'ship_to_multiple_address_blind_address',
                        'ship_to_multiple_address_extra_field',
                    ],
                },
                // Product Stocks Ops
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['productStocks'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many product stocks' }],
                    default: 'getAll',
                },
                // Product Stocks: Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPages',
                    type: 'boolean',
                    default: false,
                    displayOptions: { show: { resource: ['productStocks'], operation: ['getAll'] } },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)'
                },
                {
                    displayName: 'Product ID',
                    name: 'productStocks_product_id',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['productStocks'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Product ID to fetch stock records for',
                },
                {
                    displayName: 'Query Parameters',
                    name: 'queryParameters',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    displayOptions: { show: { resource: ['productStocks'], operation: ['getAll'] } },
                    default: {},
                    options: [
                        { displayName: 'Limit', name: 'limit', type: 'number', typeOptions: { minValue: 1, maxValue: 250 }, default: 250 },
                        { displayName: 'Offset', name: 'offset', type: 'number', typeOptions: { minValue: 0 }, default: 0 },
                        { displayName: 'Page Size', name: 'pageSize', type: 'number', typeOptions: { minValue: 1, maxValue: 250 }, default: 250 },
                        { displayName: 'Page Delay (ms)', name: 'pageDelay', type: 'number', typeOptions: { minValue: 25, maxValue: 1000 }, default: 50 },
                    ],
                },
                // Status listings (additive)
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['status'] } },
                    options: [
                        { name: 'List Order Status', value: 'orderStatus', action: 'List order statuses' },
                        { name: 'List Order Product Status', value: 'orderProductStatus', action: 'List order product statuses' },
                    ],
                    default: 'orderStatus',
                },
                {
                    displayName: 'Fields',
                    name: 'statusFields',
                    type: 'multiOptions',
                    displayOptions: { show: { resource: ['status'] } },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'ID', value: 'id' },
                        { name: 'Title', value: 'title' },
                    ],
                    default: ['id', 'title'],
                },
                // Batch Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['batch'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many batches' }],
                    default: 'getAll',
                },
                {
                    displayName: 'Batch ID',
                    name: 'batch_batchId',
                    type: 'number',
                    displayOptions: { show: { resource: ['batch'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by batch ID (0 = no filter)',
                },
                {
                    displayName: 'Search',
                    name: 'batch_search',
                    type: 'string',
                    displayOptions: { show: { resource: ['batch'], operation: ['getAll'] } },
                    default: '',
                    description: 'Search string to filter batches',
                },
                {
                    displayName: 'Limit',
                    name: 'batch_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['batch'], operation: ['getAll'] } },
                    default: 20,
                    description: 'Max number of results to return',
                },
                {
                    displayName: 'Offset',
                    name: 'batch_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['batch'], operation: ['getAll'] } },
                    default: 0,
                },
                // Quote Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['quote'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many quotes' }],
                    default: 'getAll',
                },
                {
                    displayName: 'Quote ID',
                    name: 'quote_quoteId',
                    type: 'number',
                    displayOptions: { show: { resource: ['quote'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by quote ID (0 = no filter)',
                },
                {
                    displayName: 'User ID',
                    name: 'quote_userId',
                    type: 'number',
                    displayOptions: { show: { resource: ['quote'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by user/customer ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'quote_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['quote'], operation: ['getAll'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'quote_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['quote'], operation: ['getAll'] } },
                    default: 0,
                },
                // Quote Product Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['quoteProduct'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many quote products' }],
                    default: 'getAll',
                },
                {
                    displayName: 'Quote ID',
                    name: 'quoteProduct_quoteId',
                    type: 'number',
                    displayOptions: { show: { resource: ['quoteProduct'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by quote ID (0 = no filter)',
                },
                {
                    displayName: 'Quote Products ID',
                    name: 'quoteProduct_quoteProductsId',
                    type: 'number',
                    displayOptions: { show: { resource: ['quoteProduct'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by quote products ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'quoteProduct_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['quoteProduct'], operation: ['getAll'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'quoteProduct_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['quoteProduct'], operation: ['getAll'] } },
                    default: 0,
                },
                // Store Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['store'] } },
                    options: [
                        { name: 'Get Many (Store Details)', value: 'getAll', action: 'Get many stores' },
                        { name: 'Countries', value: 'get_countries', action: 'Get countries' },
                        { name: 'Markup Master', value: 'get_store_markup', action: 'Get store markup masters' },
                        { name: 'Get Payment Terms', value: 'get_payment_term_master', action: 'Get payment terms' },
                        { name: 'Store Address', value: 'storeaddress', action: 'Get store addresses' },
                        { name: 'Store Credit Summary (Staging)', value: 'storeCreditSummary', action: 'Get store credit summary' },
                        { name: 'Account Summary (Staging)', value: 'accountSummary', action: 'Get account summary' },
                    ],
                    default: 'getAll',
                },
                {
                    displayName: 'Corporate ID',
                    name: 'store_corporateId',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by corporate ID (0 = no filter)',
                },
                {
                    displayName: 'Email',
                    name: 'store_email',
                    type: 'string',
                    displayOptions: { show: { resource: ['store'], operation: ['getAll'] } },
                    default: '',
                    description: 'Filter by email',
                },
                {
                    displayName: 'Status',
                    name: 'store_status',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by status',
                },
                {
                    displayName: 'Limit',
                    name: 'store_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['getAll'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'store_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['getAll'] } },
                    default: 0,
                },
                // Store: Countries (get_countries)
                {
                    displayName: 'Countries ID',
                    name: 'countries_countries_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_countries'] } },
                    default: 0,
                    description: 'Filter by countries ID (0 = no filter)',
                },
                {
                    displayName: 'Status',
                    name: 'countries_status',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_countries'] } },
                    default: 0,
                    description: 'Filter by status (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'countries_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_countries'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'countries_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_countries'] } },
                    default: 0,
                },
                // Store: Markup Master (get_store_markup)
                {
                    displayName: 'Corporate Markup ID',
                    name: 'store_markup_corporate_markup_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_store_markup'] } },
                    default: 0,
                    description: 'Filter by corporate markup ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'store_markup_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_store_markup'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'store_markup_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_store_markup'] } },
                    default: 0,
                },
                // Store: Payment Terms (get_payment_term_master)
                {
                    displayName: 'Term ID',
                    name: 'payment_term_term_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_payment_term_master'] } },
                    default: 0,
                    description: 'Filter by term ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'payment_term_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_payment_term_master'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'payment_term_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['get_payment_term_master'] } },
                    default: 0,
                },
                // Store: Store Address (storeaddress)
                {
                    displayName: 'Corporate ID',
                    name: 'storeaddress_corporate_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['storeaddress'] } },
                    default: 0,
                    description: 'Filter by corporate ID (0 = no filter)',
                },
                {
                    displayName: 'Corporate Address ID',
                    name: 'storeaddress_corporate_address_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['storeaddress'] } },
                    default: 0,
                    description: 'Filter by corporate address ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'storeaddress_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['storeaddress'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'storeaddress_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['storeaddress'] } },
                    default: 0,
                },
                // Store: Store Credit Summary (storeCreditSummary) — Staging
                {
                    displayName: 'Store ID',
                    name: 'storeCreditSummary_storeid',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['storeCreditSummary'] } },
                    default: 0,
                    description: 'Filter by store ID (0 = no filter)',
                },
                {
                    displayName: 'User ID',
                    name: 'storeCreditSummary_user_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['storeCreditSummary'] } },
                    default: 0,
                    description: 'Filter by user ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'storeCreditSummary_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['storeCreditSummary'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'storeCreditSummary_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['storeCreditSummary'] } },
                    default: 0,
                },
                // Store: Account Summary (accountSummary) — Staging
                {
                    displayName: 'Store ID',
                    name: 'accountSummary_storeid',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['accountSummary'] } },
                    default: 0,
                    description: 'Filter by store ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'accountSummary_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['accountSummary'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'accountSummary_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['store'], operation: ['accountSummary'] } },
                    default: 0,
                },
                // Department Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['department'] } },
                    options: [{ name: 'Get Many', value: 'getAll', action: 'Get many departments' }],
                    default: 'getAll',
                },
                {
                    displayName: 'Department ID',
                    name: 'department_departmentId',
                    type: 'number',
                    displayOptions: { show: { resource: ['department'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by department ID (0 = no filter)',
                },
                {
                    displayName: 'Corporate ID',
                    name: 'department_corporateId',
                    type: 'number',
                    displayOptions: { show: { resource: ['department'], operation: ['getAll'] } },
                    default: 0,
                    description: 'Filter by corporate ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'department_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['department'], operation: ['getAll'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'department_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['department'], operation: ['getAll'] } },
                    default: 0,
                },
                // Mutations (additive)
                // NOTE: Prefer "Product > Update Stock" for inventory updates; "Mutation > Update Product Stock" exists to mirror the official Postman collection.
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: { show: { resource: ['mutation'] } },
                    options: [
                        { name: 'Add Proof Version', value: 'addProofVersion', action: 'Add proof version to order product' },
                        { name: 'Assign Options', value: 'setAssignOptions', action: 'Assign options to a product' },
                        { name: 'Modify Order Product (Beta)', value: 'modifyOrderProduct', action: 'Modify order products (beta)' },
                        { name: 'Notify User', value: 'notifyUser', action: 'Notify a user' },
                        { name: 'Set Batch', value: 'setBatch', action: 'Create or update a batch' },
                        { name: 'Set Customer', value: 'setCustomer', action: 'Create or update a customer' },
                        { name: 'Set Customer Address (Staging)', value: 'setCustomerAddressDetail', action: 'Create or update a customer address (staging)' },
                        { name: 'Set Department', value: 'setDepartment', action: 'Create or update a department' },
                        { name: 'Set FAQ', value: 'setFaq', action: 'Create or update an FAQ' },
                        { name: 'Set FAQ Category', value: 'setFaqCategory', action: 'Create or update an FAQ category' },
                        { name: 'Set Master Option', value: 'setMasterOption', action: 'Create or update a master option' },
                        { name: 'Set Master Option Attribute Price', value: 'setMasterOptionAttributePrice', action: 'Create or update master option attribute prices' },
                        { name: 'Set Master Option Attributes', value: 'setMasterOptionAttributes', action: 'Create or update master option attributes' },
                        { name: 'Set Master Option Range', value: 'setMasterOptionRange', action: 'Create or update master option ranges' },
                        { name: 'Set Master Option Tags', value: 'setMasterOptionTag', action: 'Create or update master option tags' },
                        { name: 'Set Option Formulas', value: 'setCustomFormula', action: 'Create or update custom formulas' },
                        { name: 'Set Option Group', value: 'setOptionGroup', action: 'Create or update option groups' },
                        { name: 'Set Order Product', value: 'setOrderProduct', action: 'Update an order product' },
                        { name: 'Set Order (Staging)', value: 'setOrder', action: 'Create or update an order (staging)' },
                        { name: 'Set Product', value: 'setProduct', action: 'Create or update a product' },
                        { name: 'Set Product Additional Option (Beta)', value: 'setAdditionalOption', action: 'Create or update an additional option (beta)' },
                        { name: 'Set Product Additional Option Attribute (Beta)', value: 'setAdditionalOptionAttributes', action: 'Create or update an additional option attribute (beta)' },
                        { name: 'Set Product Additional Option Attribute Price (Beta)', value: 'setProductsAttributePrice', action: 'Create or update an additional option attribute price (beta)' },
                        { name: 'Set Product Design', value: 'setProductDesign', action: 'Update product design links' },
                        { name: 'Set Product Price', value: 'setProductPrice', action: 'Create or update product price' },
                        { name: 'Set Product Category', value: 'setProductCategory', action: 'Create or update a product category' },
                        { name: 'Set Product Pages', value: 'setProductPages', action: 'Create or update product pages' },
                        { name: 'Set Product Option Rules', value: 'setProductOptionRules', action: 'Create or update product option rules' },
                        { name: 'Set Product Size', value: 'setProductSize', action: 'Create or update product size variant' },
                        { name: 'Set Quote', value: 'setQuote', action: 'Create or update a quote' },
                        { name: 'Set Quantity Based Attribute Price (Beta)', value: 'setQuantityBasedAttributePrice', action: 'Create or update quantity based attribute prices (beta)' },
                        { name: 'Set Shipment', value: 'setShipment', action: 'Create or update a shipment' },
                        { name: 'Set Store Address', value: 'setStoreAddress', action: 'Create or update a store address' },
                        { name: 'Set Store', value: 'setStore', action: 'Create or update a store' },
                        { name: 'Set Store Markup', value: 'setStoreMarkup', action: 'Create or update store markup' },
                        { name: 'Set User Basket (Test)', value: 'setUserBasket', action: 'Create or update a user basket (test)' },
                        { name: 'Update Order Product Images', value: 'updateOrderProductImages', action: 'Update order product images' },
                        { name: 'Update Order Status', value: 'updateOrderStatus', action: 'Update order or order product status' },
                        { name: 'Update Product Stock', value: 'updateProductStock', action: 'Update product stock' },
                        { name: 'Update Ziflow Link (Images)', value: 'updateZiflowLinkImages', action: 'Update ziflow link images wise' },
                    ],
                    default: 'updateOrderStatus',
                },
                // Mutation: Update Order Status
                {
                    displayName: 'Type',
                    name: 'statusUpdateType',
                    type: 'options',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateOrderStatus'] } },
                    options: [
                        { name: 'Order', value: 'order' },
                        { name: 'Product', value: 'product' },
                    ],
                    default: 'order',
                    description: 'Whether to update an order-level or order-product-level status',
                },
                {
                    displayName: 'Orders ID',
                    name: 'orders_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateOrderStatus'], statusUpdateType: ['order'] } },
                    default: 0,
                    description: 'The order ID (for order-level status updates)',
                },
                {
                    displayName: 'Orders Products ID',
                    name: 'orders_products_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateOrderStatus'], statusUpdateType: ['product'] } },
                    default: 0,
                    description: 'The order-product ID (for product-level status updates)',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'updateOrderStatusInput',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateOrderStatus'] } },
                    default: '{\n  "order_product_status": "Awaiting Artwork",\n  "comment": "",\n  "notify": 0\n}',
                    description: 'UpdateOrderStatusInput object with order_product_status, comment, notify (0 or 1)',
                },
                // Mutation: Set Order Product
                {
                    displayName: 'Order Product ID',
                    name: 'setOrderProduct_order_product_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrderProduct'] } },
                    default: 0,
                    description: 'The order-product ID to update',
                },
                {
                    displayName: 'Width',
                    name: 'setOrderProduct_width',
                    type: 'number',
                    typeOptions: { numberPrecision: 2 },
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrderProduct'] } },
                    default: 0,
                },
                {
                    displayName: 'Height',
                    name: 'setOrderProduct_height',
                    type: 'number',
                    typeOptions: { numberPrecision: 2 },
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrderProduct'] } },
                    default: 0,
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setOrderProduct_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrderProduct'] } },
                    default: '{\n  "lock_price": 0,\n  "comment": "",\n  "notify_customer": 0\n}',
                    description: 'SetOrderProductInput JSON object',
                },
                // Mutation: Set Batch
                {
                    displayName: 'Batch ID',
                    name: 'setBatch_batch_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setBatch'] } },
                    default: 0,
                    description: 'Batch ID (0 to create new)',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setBatch_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setBatch'] } },
                    default: '{\n  "batch_name": "",\n  "nesting_size": "",\n  "nest_width": 0,\n  "nest_height": 0,\n  "print_count": 1,\n  "send_mail": 0,\n  "print_instructions": [],\n  "finishing_instructions": [],\n  "front_print_filename": "",\n  "front_cut_filename": "",\n  "front_image_link": "",\n  "rear_print_filename": "",\n  "rear_cut_filename": "",\n  "rear_image_link": "",\n  "jobs": []\n}',
                    description: 'SetBatchMasterInput JSON object',
                },
                // Mutation: Set Product
                {
                    displayName: 'Input (JSON)',
                    name: 'setProduct_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProduct'] } },
                    default: '{\n  "category_id": 0,\n  "visible": 1,\n  "products_title": "",\n  "products_internal_title": ""\n}',
                    description: 'ProductInput JSON object',
                },
                // Mutation: Set Product Price
                {
                    displayName: 'Input (JSON)',
                    name: 'setProductPrice_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductPrice'] } },
                    default: '{\n  "product_price_id": 0,\n  "products_id": 0,\n  "qty": 1,\n  "qty_to": 100,\n  "price": 0,\n  "vendor_price": 0,\n  "size_id": 0,\n  "visible": "1"\n}',
                    description: 'ProductPriceInput JSON object',
                },
                // Mutation: Set Product Size
                {
                    displayName: 'Input (JSON)',
                    name: 'setProductSize_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductSize'] } },
                    default: '{\n  "product_size_id": 0,\n  "products_id": 0,\n  "size_name": "",\n  "color_name": "",\n  "products_sku": "",\n  "visible": 1\n}',
                    description: 'ProductSizeInput JSON object. Set product_size_id to 0 to create new.',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setProductCategory_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductCategory'] } },
                    default: '{\n  "category_id": 0,\n  "category_name": "",\n  "parent_id": 0,\n  "visible": 1\n}',
                    description: 'ProductCategoryInput JSON object. Set category_id to 0 to create new.',
                },
                // Mutation: Set Quote
                {
                    displayName: 'User ID',
                    name: 'setQuote_userid',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setQuote'] } },
                    default: 0,
                },
                {
                    displayName: 'Quote ID',
                    name: 'setQuote_quote_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setQuote'] } },
                    default: 0,
                    description: 'Quote ID (0 to create new)',
                },
                {
                    displayName: 'Quote Title',
                    name: 'setQuote_quote_title',
                    type: 'string',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setQuote'] } },
                    default: '',
                },
                {
                    displayName: 'Shipping Type',
                    name: 'setQuote_selectedShippingType',
                    type: 'string',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setQuote'] } },
                    default: '',
                    description: 'e.g. fedexground',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setQuote_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setQuote'] } },
                    default: '{\n  "productsArr": []\n}',
                    description: 'SetQuoteInput JSON object with productsArr',
                },
                // Mutation: Set Product Design
                {
                    displayName: 'Order Product ID',
                    name: 'setProductDesign_order_product_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductDesign'] } },
                    default: 0,
                },
                {
                    displayName: 'Ziflow Link',
                    name: 'setProductDesign_ziflow_link',
                    type: 'string',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductDesign'] } },
                    default: '',
                },
                {
                    displayName: 'Ziflow Preflight Link',
                    name: 'setProductDesign_ziflow_preflight_link',
                    type: 'string',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductDesign'] } },
                    default: '',
                },
                // Mutation: Update Order Product Images
                {
                    displayName: 'Order Product ID',
                    name: 'updateOrderProductImages_order_product_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateOrderProductImages'] } },
                    default: 0,
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'updateOrderProductImages_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateOrderProductImages'] } },
                    default: '{\n  "imagefiles": [\n    {\n      "thumb": "",\n      "large": "",\n      "original": "",\n      "pagename": "Front_1"\n    }\n  ]\n}',
                    description: 'SetOrderProductImageInput JSON object with imagefiles array',
                },
                // Mutation: Add Proof Version
                {
                    displayName: 'Order Product ID',
                    name: 'addProofVersion_order_product_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['addProofVersion'] } },
                    default: 0,
                },
                {
                    displayName: 'Add Version File Only',
                    name: 'addProofVersion_add_version_file_only',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['addProofVersion'] } },
                    default: 1,
                    description: 'Set to 1 to add version file only',
                },
                {
                    displayName: 'Ask For Approval',
                    name: 'addProofVersion_ask_for_approval',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['addProofVersion'] } },
                    default: 0,
                    description: 'Set to 1 to ask for approval',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'addProofVersion_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['addProofVersion'] } },
                    default: '{\n  "imagefiles": []\n}',
                    description: 'SetOrderProductImageInput JSON with imagefiles array containing version metadata',
                },
                // Mutation: Update Ziflow Link (Images)
                {
                    displayName: 'Order Product ID',
                    name: 'updateZiflowLinkImages_order_product_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateZiflowLinkImages'] } },
                    default: 0,
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'updateZiflowLinkImages_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateZiflowLinkImages'] } },
                    default: '{\n  "imagefiles": [\n    {\n      "pagename": "Front_1",\n      "ziflow_link": "",\n      "ziflow_preflight_link": ""\n    }\n  ]\n}',
                    description: 'SetOrderProductImageInput JSON with ziflow links per image',
                },
                // Mutation: Notify User
                {
                    displayName: 'User Type',
                    name: 'notifyUser_usertype',
                    type: 'options',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['notifyUser'] } },
                    options: [
                        { name: 'Admin', value: 'admin' },
                        { name: 'Customer', value: 'customer' },
                    ],
                    default: 'admin',
                },
                {
                    displayName: 'Customer ID',
                    name: 'notifyUser_cust_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['notifyUser'] } },
                    default: 0,
                    description: 'Customer ID (0 = omit)',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'notifyUser_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['notifyUser'] } },
                    default: '{\n  \"cc\": \"\",\n  \"body\": \"<h1>Hello</h1>\",\n  \"subject\": \"\"\n}',
                    description: 'UserNotifyInput JSON with cc, body (HTML), subject',
                },
                // Mutation: Set Shipment
                {
                    displayName: 'Order ID',
                    name: 'setShipment_order_id',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setShipment'] } },
                    default: 0,
                },
                {
                    displayName: 'Shipment ID',
                    name: 'setShipment_shipment_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setShipment'] } },
                    default: 0,
                    description: 'Shipment ID (0 to create new)',
                },
                {
                    displayName: 'Tracking Number',
                    name: 'setShipment_tracking_number',
                    type: 'string',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setShipment'] } },
                    default: '',
                },
                {
                    displayName: 'Shipment Info (JSON)',
                    name: 'setShipment_shipmentinfo',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setShipment'] } },
                    default: '[\n  {\n    \"packageinfo\": [\n      {\n        \"weight\": 0,\n        \"length\": 0,\n        \"width\": 0,\n        \"height\": 0,\n        \"tracking\": \"\",\n        \"opdata\": [\n          { \"opid\": 0, \"qty\": \"1\" }\n        ]\n      }\n    ]\n  }\n]',
                    description: 'shipmentinfo JSON (array with packageinfo) per OPS contract',
                },
                // Mutation: Set Customer (direct mutation)
                {
                    displayName: 'Customer ID',
                    name: 'setCustomer_customer_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setCustomer'] } },
                    default: 0,
                    description: 'Customer ID (0 to create new)',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setCustomer_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setCustomer'] } },
                    default: '{\n  \"registration_type\": 0,\n  \"corporateid\": 0,\n  \"departmentid\": 0,\n  \"first_name\": \"\",\n  \"last_name\": \"\",\n  \"email\": \"\",\n  \"password\": \"\",\n  \"set_password\": 1,\n  \"phone_no\": \"\",\n  \"company_name\": \"\",\n  \"user_group\": 0,\n  \"secondary_emails\": \"\",\n  \"status\": 1,\n  \"tax_exemption\": 0,\n  \"payon_account\": 0,\n  \"payon_limit\": 0\n}',
                    description: 'SetCustomerInput JSON object',
                },
                // Mutation: Set Customer Address Detail (Staging)
                {
                    displayName: 'Input (JSON)',
                    name: 'setCustomerAddressDetail_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setCustomerAddressDetail'] } },
                    default: '{\n  \"user_id\": 0,\n  \"address_book_id\": 0,\n  \"firstname\": \"\",\n  \"lastname\": \"\",\n  \"companyname\": \"\",\n  \"street_address\": \"\",\n  \"suburb\": \"\",\n  \"postcode\": \"\",\n  \"city\": \"\",\n  \"state\": \"\",\n  \"country\": \"\",\n  \"phone_number\": \"\"\n}',
                    description: 'CustomerAddressInput JSON object',
                },
                // Mutation: Set Product Option Rules
                {
                    displayName: 'Input (JSON)',
                    name: 'setProductOptionRules_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductOptionRules'] } },
                    default: '{\n  \"rule_id\": 0,\n  \"rule_name\": \"\",\n  \"rule_type\": \"\",\n  \"delete\": 0\n}',
                    description: 'ProductOptionRulesInput JSON object',
                },
                // Mutation: Set Custom Formula
                {
                    displayName: 'Input (JSON)',
                    name: 'setCustomFormula_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setCustomFormula'] } },
                    default: '{\n  \"formula_id\": 0,\n  \"formula_label\": \"\",\n  \"formula_syntax\": \"\",\n  \"delete\": 0\n}',
                    description: 'CustomFormulaInput JSON object',
                },
                // Mutation: Set Option Group
                {
                    displayName: 'Input (JSON)',
                    name: 'setOptionGroup_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOptionGroup'] } },
                    default: '{\n  \"prod_add_opt_group_id\": 0,\n  \"opt_group_name\": \"\",\n  \"use_for\": \"0\",\n  \"display_style\": \"0\",\n  \"option_count\": 0,\n  \"is_collapse\": \"0\",\n  \"sort_order\": 0,\n  \"delete\": 0\n}',
                    description: 'OptionGroupInput JSON object',
                },
                // Mutation: Set Master Option Tag
                {
                    displayName: 'Input (JSON)',
                    name: 'setMasterOptionTag_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setMasterOptionTag'] } },
                    default: '{\n  \"master_option_tag_id\": 0,\n  \"master_option_tag_name\": \"\",\n  \"delete\": 0\n}',
                    description: 'MasterOptionTagInput JSON object',
                },
                // Mutation: Set Master Option Attributes
                {
                    displayName: 'Input (JSON)',
                    name: 'setMasterOptionAttributes_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setMasterOptionAttributes'] } },
                    default: '{\n  \"master_attribute_id\": 0,\n  \"master_option_id\": 0,\n  \"label\": \"\",\n  \"delete\": 0\n}',
                    description: 'MasterOptionAttributesInput JSON object',
                },
                // Mutation: Set Master Option Range
                {
                    displayName: 'Input (JSON)',
                    name: 'setMasterOptionRange_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setMasterOptionRange'] } },
                    default: '{\n  \"option_id\": 0,\n  \"ranges\": [\n    { \"from_range\": 1, \"to_range\": 1, \"delete\": 0 }\n  ]\n}',
                    description: 'MasterOptionRangeInput JSON object',
                },
                // Mutation: Set Master Option Attribute Price
                {
                    displayName: 'Input (JSON)',
                    name: 'setMasterOptionAttributePrice_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setMasterOptionAttributePrice'] } },
                    default: '{\n  \"attr_id\": 0,\n  \"delete\": 0,\n  \"prices\": [\n    { \"range_id\": 0, \"price\": 0, \"vendor_price\": 0, \"site_admin_markup\": 0 }\n  ]\n}',
                    description: 'MasterOptionAttributePriceInput JSON object',
                },
                // Mutation: Set Master Option
                {
                    displayName: 'Input (JSON)',
                    name: 'setMasterOption_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setMasterOption'] } },
                    default: '{\n  \"master_option_id\": 0,\n  \"title\": \"\",\n  \"description\": \"\",\n  \"options_type\": \"combo\",\n  \"status\": \"1\",\n  \"delete\": 0\n}',
                    description: 'MasterOptionInput JSON object',
                },
                // Mutation: Assign Options
                {
                    displayName: 'Input (JSON)',
                    name: 'setAssignOptions_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setAssignOptions'] } },
                    default: '{\n  \"products_id\": 0,\n  \"master_option_id\": 0,\n  \"attribute_ids\": [],\n  \"setup_cost\": 0\n}',
                    description: 'AssignOptionsInput JSON object',
                },
                // Mutation: Set Product Pages
                {
                    displayName: 'Input (JSON)',
                    name: 'setProductPages_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductPages'] } },
                    default: '{\n  \"pages_id\": 0,\n  \"products_id\": 0,\n  \"page_title\": \"\",\n  \"sort_order\": 0,\n  \"visible\": \"1\"\n}',
                    description: 'ProductPagesInput JSON object',
                },
                // Mutation: Set Store Address
                {
                    displayName: 'Input (JSON)',
                    name: 'setStoreAddress_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setStoreAddress'] } },
                    default: '{\n  \"corporate_address_id\": 0,\n  \"corporate_id\": 0,\n  \"department_id\": 0,\n  \"office_name\": \"\",\n  \"available_to\": \"c\",\n  \"corporate_address\": \"\",\n  \"city\": \"\",\n  \"state\": \"\",\n  \"country\": \"\",\n  \"postcode\": \"\",\n  \"phone_number\": \"\",\n  \"status\": \"1\",\n  \"delete\": 0\n}',
                    description: 'StoreAddressInput JSON object',
                },
                // Mutation: Set Department
                {
                    displayName: 'Input (JSON)',
                    name: 'setDepartment_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setDepartment'] } },
                    default: '{\n  \"department_id\": 0,\n  \"corporate_id\": 0,\n  \"name\": \"\",\n  \"email_to\": \"\",\n  \"status\": \"1\",\n  \"delete\": 0\n}',
                    description: 'DepartmentInput JSON object',
                },
                // Mutation: Set Store
                {
                    displayName: 'Input (JSON)',
                    name: 'setStore_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setStore'] } },
                    default: '{\n  \"corporate_id\": 0,\n  \"email\": \"\",\n  \"username\": \"\",\n  \"password\": \"\",\n  \"corporate_name\": \"\",\n  \"status\": \"1\"\n}',
                    description: 'StoreInput JSON object',
                },
                // Mutation: Set Store Markup
                {
                    displayName: 'Input (JSON)',
                    name: 'setStoreMarkup_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setStoreMarkup'] } },
                    default: '{\n  \"corporate_markup_id\": 0,\n  \"markup_title\": \"\",\n  \"markup_details\": \"\",\n  \"status\": \"1\",\n  \"appliedon\": \"1\",\n  \"delete\": 0\n}',
                    description: 'StoreMarkupInput JSON object',
                },
                // Mutation: Set FAQ Category
                {
                    displayName: 'Input (JSON)',
                    name: 'setFaqCategory_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setFaqCategory'] } },
                    default: '{\n  \"faqcat_id\": 0,\n  \"faq_category_name\": \"\",\n  \"status\": \"1\",\n  \"sort_order\": 0,\n  \"delete\": 0\n}',
                    description: 'FaqCategoryInput JSON object',
                },
                // Mutation: Set FAQ
                {
                    displayName: 'Input (JSON)',
                    name: 'setFaq_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setFaq'] } },
                    default: '{\n  \"faq_id\": 0,\n  \"faqcat_id\": 0,\n  \"status\": \"1\",\n  \"sort_order\": 0,\n  \"faq_type\": \"G\",\n  \"faq_question\": \"\",\n  \"faq_answer\": \"\"\n}',
                    description: 'FaqInput JSON object',
                },
                // Mutation: Set Order (Staging)
                {
                    displayName: 'User ID',
                    name: 'setOrder_userid',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrder'] } },
                    default: 0,
                },
                {
                    displayName: 'Order ID',
                    name: 'setOrder_order_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrder'] } },
                    default: 0,
                    description: 'Order ID (0 to create new)',
                },
                {
                    displayName: 'Order Title',
                    name: 'setOrder_order_title',
                    type: 'string',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrder'] } },
                    default: '',
                },
                {
                    displayName: 'Shipping Type ID',
                    name: 'setOrder_selectedShippingType',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrder'] } },
                    default: 0,
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setOrder_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setOrder'] } },
                    default: '{\n  \"productsArr\": []\n}',
                    description: 'SetOrderInput JSON object with productsArr',
                },
                // Mutation: Set User Basket (TEST)
                {
                    displayName: 'User ID',
                    name: 'setUserBasket_userId',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setUserBasket'] } },
                    default: 0,
                },
                {
                    displayName: 'Action',
                    name: 'setUserBasket_action',
                    type: 'string',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setUserBasket'] } },
                    default: 'add',
                    description: 'e.g. add, update, remove',
                },
                {
                    displayName: 'Basket ID',
                    name: 'setUserBasket_basketId',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['setUserBasket'] } },
                    default: 0,
                    description: 'Basket ID (0 to create new)',
                },
                {
                    displayName: 'Item Index',
                    name: 'setUserBasket_itemIndex',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setUserBasket'] } },
                    default: 0,
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setUserBasket_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setUserBasket'] } },
                    default: '{\n  \"items\": []\n}',
                    description: 'SetUserBasketInput JSON object',
                },
                // Mutation: Modify Order Product (Beta)
                {
                    displayName: 'Order ID',
                    name: 'modifyOrderProduct_orderid',
                    type: 'number',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['modifyOrderProduct'] } },
                    default: 0,
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'modifyOrderProduct_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['modifyOrderProduct'] } },
                    default: '{\n  \"productArr\": []\n}',
                    description: 'ModifyOrderProductInput JSON object',
                },
                // Mutation: Additional Option (Beta)
                {
                    displayName: 'Input (JSON)',
                    name: 'setAdditionalOption_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setAdditionalOption'] } },
                    default: '{\n  \"prod_add_opt_id\": 0,\n  \"products_id\": 0,\n  \"title\": \"\",\n  \"options_type\": \"radio\",\n  \"status\": \"1\",\n  \"delete\": 0\n}',
                    description: 'AdditionalOptionInput JSON object',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setAdditionalOptionAttributes_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setAdditionalOptionAttributes'] } },
                    default: '{\n  \"attribute_id\": 0,\n  \"prod_add_opt_id\": 0,\n  \"label\": \"\",\n  \"status\": \"1\",\n  \"delete\": 0\n}',
                    description: 'AdditionalOptionAttributesInput JSON object',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setProductsAttributePrice_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setProductsAttributePrice'] } },
                    default: '{\n  \"attribute_id\": 0,\n  \"size_from\": 0,\n  \"size_to\": 0,\n  \"attributes_price\": 0,\n  \"vendor_price\": 0,\n  \"site_admin_markup\": 0,\n  \"delete\": 0\n}',
                    description: 'ProductsAttributePriceInput JSON object',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'setQuantityBasedAttributePrice_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['setQuantityBasedAttributePrice'] } },
                    default: '{\n  \"attribute_id\": 0,\n  \"size_from\": 0,\n  \"size_to\": 0,\n  \"quantity_from\": 0,\n  \"quantity_to\": 0,\n  \"attribute_price\": 0,\n  \"vendor_price\": 0,\n  \"site_admin_markup\": 0,\n  \"delete\": 0\n}',
                    description: 'QuantityBasedAttributePriceInput JSON object',
                },
                // Mutation: Update Product Stock
                {
                    displayName: 'Stock ID',
                    name: 'updateProductStock_stock_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateProductStock'] } },
                    default: 0,
                    description: 'Stock ID (recommended). If provided, product SKU is optional.',
                },
                {
                    displayName: 'Product SKU',
                    name: 'updateProductStock_product_sku',
                    type: 'string',
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateProductStock'] } },
                    default: '',
                    description: 'Product SKU (optional if Stock ID provided)',
                },
                {
                    displayName: 'Action',
                    name: 'updateProductStock_action',
                    type: 'options',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateProductStock'] } },
                    options: [
                        { name: 'Add', value: 'Add' },
                        { name: 'Remove', value: 'Remove' },
                        { name: 'Reset', value: 'Reset' },
                    ],
                    default: 'Add',
                },
                {
                    displayName: 'Input (JSON)',
                    name: 'updateProductStock_input',
                    type: 'json',
                    required: true,
                    displayOptions: { show: { resource: ['mutation'], operation: ['updateProductStock'] } },
                    default: '{\n  \"stock_quantity\": 0,\n  \"comment\": \"\"\n}',
                    description: 'UpdateProductStockInput JSON object',
                },
                // Customer Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                        },
                    },
                    options: [
                        {
                            name: 'Get',
                            value: 'get',
                            description: 'Get a customer by email',
                            action: 'Get a customer',
                        },
                        {
                            name: 'Get Many',
                            value: 'getAll',
                            description: 'Get many customers',
                            action: 'Get many customers',
                        },
                        {
                            name: 'Get User Basket (Test)',
                            value: 'getUserBasket',
                            description: 'Get user basket by user ID',
                            action: 'Get a user basket',
                        },
                        {
                            name: 'Create',
                            value: 'create',
                            description: 'Create a new customer',
                            action: 'Create a customer',
                        },
                        {
                            name: 'Update',
                            value: 'update',
                            description: 'Update an existing customer',
                            action: 'Update a customer',
                        },
                    ],
                    default: 'get',
                },
                // Customer: Get User Basket (getUserBasket) — TEST
                {
                    displayName: 'User ID',
                    name: 'userBasket_user_id',
                    type: 'number',
                    required: true,
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['getUserBasket'],
                        },
                    },
                    default: 0,
                    description: 'User ID to fetch basket for',
                },
                // Customer: Get - Email Field
                {
                    displayName: 'Email',
                    name: 'email',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['get'],
                        },
                    },
                    description: 'Email address of the customer to retrieve',
                },
                // Customer: Get - Fields Selection
                {
                    displayName: 'Customer Fields',
                    name: 'customerFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Customer Fields', value: 'SELECT_ALL_CUSTOMER' },
                        { name: '🔘 Deselect All Customer Fields', value: 'DESELECT_ALL_CUSTOMER' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'User ID', value: 'userid' },
                        { name: 'User Type', value: 'user_type' },
                        { name: 'Customer Name', value: 'customers_name' },
                        { name: 'First Name', value: 'customers_first_name' },
                        { name: 'Last Name', value: 'customers_last_name' },
                        { name: 'Company', value: 'customers_company' },
                        { name: 'Telephone', value: 'customers_telephone' },
                        { name: 'Email Address', value: 'customers_email_address' },
                        { name: 'Corporate Name', value: 'customers_corporate_name' },
                        { name: 'Status', value: 'customers_status' },
                        { name: 'Pay On Enable', value: 'customers_payon_enable' },
                        { name: 'Pay Limit', value: 'customers_pay_limit' },
                        { name: 'Balance Amount', value: 'customers_balance_amount' },
                        { name: 'Department Name', value: 'customers_department_name' },
                        { name: 'User Group Name', value: 'customers_user_group_name' },
                        { name: 'Register Date', value: 'customers_register_date' },
                        { name: 'Username', value: 'customers_username' },
                        { name: 'Secondary Emails', value: 'customers_secondary_emails' },
                        { name: 'Reward Points', value: 'reward_points' },
                    ],
                    default: [
                        'userid',
                        'customers_name',
                        'customers_first_name',
                        'customers_last_name',
                        'customers_email_address',
                        'customers_telephone',
                        'customers_status',
                    ],
                    description: 'Select customer fields to return. Use "Select All" or "Deselect All" options at the top of the list.',
                },
                // Customer: Get - Address Fields Selection
                {
                    displayName: 'Address Fields',
                    name: 'addressFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Address Fields', value: 'SELECT_ALL_ADDRESS' },
                        { name: '🔘 Deselect All Address Fields', value: 'DESELECT_ALL_ADDRESS' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Name', value: 'name' },
                        { name: 'First Name', value: 'first_name' },
                        { name: 'Last Name', value: 'last_name' },
                        { name: 'Company', value: 'company' },
                        { name: 'Street Address', value: 'street_address' },
                        { name: 'Suburb', value: 'suburb' },
                        { name: 'City', value: 'city' },
                        { name: 'Postcode', value: 'postcode' },
                        { name: 'State', value: 'state' },
                        { name: 'Country', value: 'country' },
                        { name: 'Telephone', value: 'telephone' },
                        { name: 'Address Type', value: 'address_type' },
                        { name: 'Is Default Address', value: 'is_default_address' },
                        { name: 'Extra Field', value: 'extrafield' },
                    ],
                    default: [
                        'name',
                        'street_address',
                        'city',
                        'postcode',
                        'state',
                        'country',
                        'telephone',
                    ],
                    description: 'Select address fields to return. Use "Select All" or "Deselect All" options at the top. Leave empty to exclude address details.',
                },
                // Customer: Create - Required Fields
                {
                    displayName: 'Registration Type',
                    name: 'registration_type',
                    type: 'options',
                    required: true,
                    default: 1,
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['create'],
                        },
                    },
                    options: [
                        { name: 'Two Step Register', value: 1 },
                        { name: 'Normal Register', value: 0 },
                    ],
                    description: 'Registration type - Two Step sends email for completion, Normal creates fully registered customer',
                },
                {
                    displayName: 'First Name',
                    name: 'first_name',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['create'],
                        },
                    },
                    description: 'Customer first name',
                },
                {
                    displayName: 'Last Name',
                    name: 'last_name',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['create'],
                        },
                    },
                    description: 'Customer last name',
                },
                {
                    displayName: 'Email',
                    name: 'email',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['create'],
                        },
                    },
                    description: 'Customer email address',
                },
                // Customer: Create - Optional Fields
                {
                    displayName: 'Optional Fields',
                    name: 'optionalFields',
                    type: 'collection',
                    placeholder: 'Add Field',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['create'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Corporate ID',
                            name: 'corporateid',
                            type: 'number',
                            default: 0,
                            description: 'Store ID or 0 for default store',
                        },
                        {
                            displayName: 'Phone Number',
                            name: 'phone_no',
                            type: 'string',
                            default: '',
                            description: 'Customer phone number',
                        },
                        {
                            displayName: 'Company Name',
                            name: 'company_name',
                            type: 'string',
                            default: '',
                            description: 'Customer company name',
                        },
                        {
                            displayName: 'Password',
                            name: 'password',
                            type: 'string',
                            default: '',
                            description: 'Customer password (auto-generated if empty for full registration)',
                        },
                        {
                            displayName: 'Status',
                            name: 'status',
                            type: 'number',
                            default: 1,
                            description: 'Customer status (0=inactive, 1=active)',
                        },
                        {
                            displayName: 'Department ID',
                            name: 'departmentid',
                            type: 'number',
                            default: 0,
                            description: 'Department ID if any',
                        },
                        {
                            displayName: 'Set Password',
                            name: 'set_password',
                            type: 'number',
                            options: [
                                { name: 'No', value: 0 },
                                { name: 'Yes', value: 1 },
                            ],
                            default: 0,
                            description: 'Set to 1 to change password, 0 otherwise',
                        },
                        {
                            displayName: 'User Group',
                            name: 'user_group',
                            type: 'number',
                            default: 0,
                            description: 'Customer user group ID',
                        },
                        {
                            displayName: 'Secondary Emails',
                            name: 'secondary_emails',
                            type: 'string',
                            default: '',
                            description: 'Comma separated secondary emails (e.g., abc@test.com,xyz@test.com)',
                        },
                        {
                            displayName: 'Tax Exemption',
                            name: 'tax_exemption',
                            type: 'number',
                            options: [
                                { name: 'No', value: 0 },
                                { name: 'Yes', value: 1 },
                            ],
                            default: 0,
                            description: '1 if customer is tax exempted, 0 otherwise',
                        },
                        {
                            displayName: 'Payon Account',
                            name: 'payon_account',
                            type: 'number',
                            options: [
                                { name: 'Disabled', value: 0 },
                                { name: 'Enabled', value: 1 },
                            ],
                            default: 0,
                            description: '1 to enable payon for this customer, 0 otherwise',
                        },
                        {
                            displayName: 'Payon Limit',
                            name: 'payon_limit',
                            type: 'number',
                            default: 0,
                            description: 'Set payon limit for this customer (required if payon_account is 1)',
                        },
                    ],
                },
                // Customer: Update - Customer ID
                {
                    displayName: 'Customer ID',
                    name: 'customer_id',
                    type: 'number',
                    required: true,
                    default: 0,
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['update'],
                        },
                    },
                    description: 'Customer ID for update (required for update operation)',
                },
                // Customer: Update - Fields to Update
                {
                    displayName: 'Fields to Update',
                    name: 'updateFields',
                    type: 'collection',
                    placeholder: 'Add Field',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['update'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Registration Type',
                            name: 'registration_type',
                            type: 'options',
                            options: [
                                { name: 'Normal Register', value: 0 },
                                { name: 'Two Step Register', value: 1 },
                            ],
                            default: 0,
                            description: '0 for normal register, 1 for two step register',
                        },
                        {
                            displayName: 'Corporate ID',
                            name: 'corporateid',
                            type: 'number',
                            default: 0,
                            description: 'Store ID or 0 for default store',
                        },
                        {
                            displayName: 'Department ID',
                            name: 'departmentid',
                            type: 'number',
                            default: 0,
                            description: 'Department ID if any',
                        },
                        {
                            displayName: 'First Name',
                            name: 'first_name',
                            type: 'string',
                            default: '',
                            description: 'Customer first name',
                        },
                        {
                            displayName: 'Last Name',
                            name: 'last_name',
                            type: 'string',
                            default: '',
                            description: 'Customer last name',
                        },
                        {
                            displayName: 'Email',
                            name: 'email',
                            type: 'string',
                            default: '',
                            description: 'Customer email address',
                        },
                        {
                            displayName: 'Password',
                            name: 'password',
                            type: 'string',
                            default: '',
                            description: 'Customer password',
                        },
                        {
                            displayName: 'Set Password',
                            name: 'set_password',
                            type: 'number',
                            options: [
                                { name: 'No', value: 0 },
                                { name: 'Yes', value: 1 },
                            ],
                            default: 0,
                            description: 'Set to 1 to change password, 0 otherwise',
                        },
                        {
                            displayName: 'Phone Number',
                            name: 'phone_no',
                            type: 'string',
                            default: '',
                            description: 'Customer phone number',
                        },
                        {
                            displayName: 'Company Name',
                            name: 'company_name',
                            type: 'string',
                            default: '',
                            description: 'Customer company name',
                        },
                        {
                            displayName: 'User Group',
                            name: 'user_group',
                            type: 'number',
                            default: 0,
                            description: 'Customer user group ID',
                        },
                        {
                            displayName: 'Secondary Emails',
                            name: 'secondary_emails',
                            type: 'string',
                            default: '',
                            description: 'Comma separated secondary emails (e.g., abc@test.com,xyz@test.com)',
                        },
                        {
                            displayName: 'Status',
                            name: 'status',
                            type: 'number',
                            default: 0,
                            description: 'Customer status (0 or 1)',
                        },
                        {
                            displayName: 'Tax Exemption',
                            name: 'tax_exemption',
                            type: 'number',
                            options: [
                                { name: 'No', value: 0 },
                                { name: 'Yes', value: 1 },
                            ],
                            default: 0,
                            description: '1 if customer is tax exempted, 0 otherwise',
                        },
                        {
                            displayName: 'Payon Account',
                            name: 'payon_account',
                            type: 'number',
                            options: [
                                { name: 'Disabled', value: 0 },
                                { name: 'Enabled', value: 1 },
                            ],
                            default: 0,
                            description: '1 to enable payon for this customer, 0 otherwise',
                        },
                        {
                            displayName: 'Payon Limit',
                            name: 'payon_limit',
                            type: 'number',
                            default: 0,
                            description: 'Set payon limit for this customer (required if payon_account is 1)',
                        },
                    ],
                },
                // Customer: Get Many - Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPages',
                    type: 'boolean',
                    default: false,
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['getAll'],
                        },
                    },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)',
                },
                // Customer: Get Many - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParameters',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Email',
                            name: 'email',
                            type: 'string',
                            default: '',
                            description: 'Filter customers by email address',
                        },
                        {
                            displayName: 'From Date',
                            name: 'from_date',
                            type: 'dateTime',
                            default: '',
                            description: 'Filter customers from this date',
                        },
                        {
                            displayName: 'To Date',
                            name: 'to_date',
                            type: 'dateTime',
                            default: '',
                            description: 'Filter customers to this date',
                        },
                        {
                            displayName: 'Date Type',
                            name: 'date_type',
                            type: 'options',
                            options: [
                                {
                                    name: 'Registration Date',
                                    value: 'REGISTRATION',
                                },
                                {
                                    name: 'Last Modified',
                                    value: 'MODIFIED',
                                },
                            ],
                            default: 'REGISTRATION',
                            description: 'Type of date to filter by',
                        },
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of customers to return per page (max 250). Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of customers to skip. Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Page Size',
                            name: 'pageSize',
                            type: 'number',
                            typeOptions: {
                                minValue: 1,
                                maxValue: 250,
                            },
                            default: 250,
                            description: 'Records per page when "Fetch All Pages" is enabled (max 250 - API hard limit). Ignored for single page requests.',
                        },
                        {
                            displayName: 'Delay Between Pages (ms)',
                            name: 'pageDelay',
                            type: 'number',
                            typeOptions: {
                                minValue: 25,
                            },
                            default: 50,
                            description: 'Delay between API calls when "Fetch All Pages" is enabled (default 50ms for better performance, min 25ms). Ignored for single page requests.',
                        },
                    ],
                },
                // Customer: Get Many - Fields Selection
                {
                    displayName: 'Customer Fields',
                    name: 'customerFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Customer Fields', value: 'SELECT_ALL_CUSTOMER' },
                        { name: '🔘 Deselect All Customer Fields', value: 'DESELECT_ALL_CUSTOMER' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'User ID', value: 'userid' },
                        { name: 'User Type', value: 'user_type' },
                        { name: 'Customer Name', value: 'customers_name' },
                        { name: 'First Name', value: 'customers_first_name' },
                        { name: 'Last Name', value: 'customers_last_name' },
                        { name: 'Company', value: 'customers_company' },
                        { name: 'Telephone', value: 'customers_telephone' },
                        { name: 'Email Address', value: 'customers_email_address' },
                        { name: 'Corporate Name', value: 'customers_corporate_name' },
                        { name: 'Status', value: 'customers_status' },
                        { name: 'Pay On Enable', value: 'customers_payon_enable' },
                        { name: 'Pay Limit', value: 'customers_pay_limit' },
                        { name: 'Balance Amount', value: 'customers_balance_amount' },
                        { name: 'Department Name', value: 'customers_department_name' },
                        { name: 'User Group Name', value: 'customers_user_group_name' },
                        { name: 'Register Date', value: 'customers_register_date' },
                        { name: 'Username', value: 'customers_username' },
                        { name: 'Secondary Emails', value: 'customers_secondary_emails' },
                        { name: 'Reward Points', value: 'reward_points' },
                    ],
                    default: [
                        'userid',
                        'user_type',
                        'customers_name',
                        'customers_first_name',
                        'customers_last_name',
                        'customers_company',
                        'customers_telephone',
                        'customers_email_address',
                        'customers_corporate_name',
                        'customers_status',
                        'customers_payon_enable',
                        'customers_pay_limit',
                        'customers_balance_amount',
                        'customers_department_name',
                        'customers_user_group_name',
                        'customers_register_date',
                        'customers_username',
                        'customers_secondary_emails',
                        'reward_points',
                    ],
                    description: 'Select customer fields to return. All fields selected by default. Use "Select All" or "Deselect All" options at the top.',
                },
                // Customer: Get Many - Address Fields Selection
                {
                    displayName: 'Address Fields',
                    name: 'addressFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['customer'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Address Fields', value: 'SELECT_ALL_ADDRESS' },
                        { name: '🔘 Deselect All Address Fields', value: 'DESELECT_ALL_ADDRESS' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Name', value: 'name' },
                        { name: 'First Name', value: 'first_name' },
                        { name: 'Last Name', value: 'last_name' },
                        { name: 'Company', value: 'company' },
                        { name: 'Street Address', value: 'street_address' },
                        { name: 'Suburb', value: 'suburb' },
                        { name: 'City', value: 'city' },
                        { name: 'Postcode', value: 'postcode' },
                        { name: 'State', value: 'state' },
                        { name: 'Country', value: 'country' },
                        { name: 'Telephone', value: 'telephone' },
                        { name: 'Address Type', value: 'address_type' },
                        { name: 'Is Default Address', value: 'is_default_address' },
                        { name: 'Extra Field', value: 'extrafield' },
                    ],
                    default: [
                        'name',
                        'first_name',
                        'last_name',
                        'company',
                        'street_address',
                        'suburb',
                        'city',
                        'postcode',
                        'state',
                        'country',
                        'telephone',
                        'address_type',
                        'is_default_address',
                        'extrafield',
                    ],
                    description: 'Select address fields to return. All fields selected by default. Use "Select All" or "Deselect All" options at the top. Leave empty to exclude address details.',
                },
                // Order Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: {
                        show: {
                            resource: ['order'],
                        },
                    },
                    options: [
                        {
                            name: 'Get',
                            value: 'get',
                            description: 'Get a single order by ID',
                            action: 'Get an order',
                        },
                        {
                            name: 'Get Many',
                            value: 'getAll',
                            description: 'Get many orders',
                            action: 'Get many orders',
                        },
                        {
                            name: 'Get Shipments',
                            value: 'getShipments',
                            description: 'Get shipment details for an order',
                            action: 'Get order shipments',
                        },
                        {
                            name: 'Create Shipment',
                            value: 'createShipment',
                            description: 'Create a new shipment for an order',
                            action: 'Create order shipment',
                        },
                    ],
                    default: 'get',
                },
                // Order: Get - Order ID Field
                {
                    displayName: 'Order ID',
                    name: 'orderId',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['get'],
                        },
                    },
                    description: 'ID of the order to retrieve',
                },
                // Order: Get - Fields Selection
                {
                    displayName: 'Order Fields',
                    name: 'orderFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'User ID', value: 'user_id' },
                        { name: 'Orders ID', value: 'orders_id' },
                        { name: 'Corporate ID', value: 'corporate_id' },
                        { name: 'Order Status', value: 'order_status' },
                        { name: 'Orders Status ID', value: 'orders_status_id' },
                        { name: 'Orders Date Finished', value: 'orders_date_finished' },
                        { name: 'Local Orders Date Finished', value: 'local_orders_date_finished' },
                        { name: 'Shipping Mode', value: 'shipping_mode' },
                        { name: 'Courier Company Name', value: 'courirer_company_name' },
                        { name: 'Airway Bill Number', value: 'airway_bill_number' },
                        { name: 'Payment Method Name', value: 'payment_method_name' },
                        { name: 'Total Amount', value: 'total_amount' },
                        { name: 'Order Amount', value: 'order_amount' },
                        { name: 'Shipping Amount', value: 'shipping_amount' },
                        { name: 'Tax Amount', value: 'tax_amount' },
                        { name: 'Coupon Amount', value: 'coupon_amount' },
                        { name: 'Coupon Code', value: 'coupon_code' },
                        { name: 'Coupon Type', value: 'coupon_type' },
                        { name: 'Order Vendor Amount', value: 'order_vendor_amount' },
                        { name: 'Orders Due Date', value: 'orders_due_date' },
                        { name: 'Order Last Modified Date', value: 'order_last_modified_date' },
                        { name: 'Department ID', value: 'department_id' },
                        { name: 'Cost Center Code', value: 'cost_center_code' },
                        { name: 'PO Number', value: 'po_number' },
                        { name: 'Total Weight', value: 'total_weight' },
                        { name: 'Partial Payment Details', value: 'partial_payment_details' },
                        { name: 'Refund Amount', value: 'refund_amount' },
                        { name: 'Blind Shipping Charge', value: 'blind_shipping_charge' },
                        { name: 'Payment Due Date', value: 'payment_due_date' },
                        { name: 'Transaction ID', value: 'transactionid' },
                        { name: 'Sales Agent Name', value: 'sales_agent_name' },
                        { name: 'Branch Name', value: 'branch_name' },
                        { name: 'Payment Status Title', value: 'payment_status_title' },
                        { name: 'Production Due Date', value: 'production_due_date' },
                        { name: 'Payment Processing Fees', value: 'payment_processing_fees' },
                        { name: 'Payment Date', value: 'payment_date' },
                        { name: 'Shipping Type ID', value: 'shipping_type_id' },
                        { name: 'Invoice Number', value: 'invoice_number' },
                        { name: 'Invoice Date', value: 'invoice_date' },
                        { name: 'Parent Corporate ID', value: 'parent_corporate_id' },
                        { name: 'Order Name', value: 'order_name' },
                        { name: 'Orders Extrafield', value: 'orders_extrafield' },
                        { name: 'Reviewers', value: 'reviewers' },
                        { name: 'Extrafield', value: 'extrafield' },
                    ],
                    default: [
                        'user_id',
                        'orders_id',
                        'corporate_id',
                        'order_status',
                        'orders_status_id',
                        'orders_date_finished',
                        'local_orders_date_finished',
                        'shipping_mode',
                        'courirer_company_name',
                        'airway_bill_number',
                        'payment_method_name',
                        'total_amount',
                        'order_amount',
                        'shipping_amount',
                        'tax_amount',
                        'coupon_amount',
                        'coupon_code',
                        'coupon_type',
                        'order_vendor_amount',
                        'orders_due_date',
                        'order_last_modified_date',
                        'department_id',
                        'cost_center_code',
                        'po_number',
                        'total_weight',
                        'partial_payment_details',
                        'refund_amount',
                        'blind_shipping_charge',
                        'payment_due_date',
                        'transactionid',
                        'sales_agent_name',
                        'branch_name',
                        'payment_status_title',
                        'production_due_date',
                        'payment_processing_fees',
                        'payment_date',
                        'shipping_type_id',
                        'invoice_number',
                        'invoice_date',
                        'parent_corporate_id',
                        'order_name',
                        'orders_extrafield',
                        'reviewers',
                        'extrafield',
                    ],
                    description: 'Select order fields to return',
                },
                // Order: Get - Customer Fields
                {
                    displayName: 'Customer Fields',
                    name: 'customerFieldsGet',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Customer Name', value: 'customers_name' },
                        { name: 'Customer Email', value: 'customers_email_address' },
                        { name: 'Customer Phone', value: 'customers_telephone' },
                        { name: 'Customer Company', value: 'customers_company' },
                        { name: 'Customer Register Date', value: 'customers_register_date' },
                        { name: 'Customer Username', value: 'customers_username' },
                        { name: 'Customer User Group', value: 'customers_user_group_name' },
                        { name: 'Customer Department', value: 'customers_department_name' },
                        { name: 'Customer Balance', value: 'customers_balance_amount' },
                        { name: 'Customer Pay Limit', value: 'customers_pay_limit' },
                        { name: 'Customer PayOn Enable', value: 'customers_payon_enable' },
                        { name: 'Customer Status', value: 'customers_status' },
                        { name: 'Customer First Name', value: 'customers_first_name' },
                        { name: 'Customer Last Name', value: 'customers_last_name' },
                    ],
                    default: [
                        'customers_name',
                        'customers_email_address',
                        'customers_telephone',
                        'customers_company',
                    ],
                    description: 'Select customer fields to return',
                },
                // Order: Get - Product Fields
                {
                    displayName: 'Product Fields',
                    name: 'productFieldsGet',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Orders Products ID', value: 'orders_products_id' },
                        { name: 'Product Size Details', value: 'product_size_details' },
                        { name: 'Products Name', value: 'products_name' },
                        { name: 'Products Title', value: 'products_title' },
                        { name: 'Products SKU', value: 'products_sku' },
                        { name: 'Products Price', value: 'products_price' },
                        { name: 'Products Quantity', value: 'products_quantity' },
                        { name: 'Template Type', value: 'template_type' },
                        { name: 'Features Details', value: 'features_details' },
                        { name: 'Photo Print Details', value: 'photo_print_details' },
                        { name: 'Product Size', value: 'productsize' },
                        { name: 'Mass Personalization Files', value: 'mass_personalization_files' },
                        { name: 'Products Vendor Price', value: 'products_vendor_price' },
                        { name: 'Products Weight', value: 'products_weight' },
                        { name: 'Inventory Storage Days', value: 'inventory_storage_days' },
                        { name: 'Product Status ID', value: 'product_status_id' },
                        { name: 'Product Status', value: 'product_status' },
                        { name: 'Product ID', value: 'product_id' },
                        { name: 'Reference Order ID', value: 'reference_order_id' },
                        { name: 'Is Kit', value: 'is_kit' },
                        { name: 'Product Tax', value: 'product_tax' },
                        { name: 'Product Info', value: 'product_info' },
                        { name: 'Template Info', value: 'template_info' },
                        { name: 'Product Printer Name', value: 'product_printer_name' },
                        { name: 'Products Unit Price', value: 'products_unit_price' },
                        { name: 'Quote ID', value: 'quote_id' },
                        { name: 'Product Production Due Date', value: 'product_production_due_date' },
                        { name: 'Orders Products ID Pattern', value: 'orders_products_id_pattern' },
                        { name: 'Orders Products Last Modified Date', value: 'orders_products_last_modified_date' },
                        { name: 'Predefined Product Type', value: 'predefined_product_type' },
                        { name: 'Ziflow Link', value: 'ziflow_link' },
                        { name: 'Print Ready Files', value: 'print_ready_files' },
                        { name: 'Proof Files', value: 'proof_files' },
                        { name: 'Item Extra Info JSON', value: 'item_extra_info_json' },
                    ],
                    default: [
                        'orders_products_id',
                        'products_name',
                        'products_sku',
                        'products_price',
                        'products_quantity',
                        'product_status',
                    ],
                    description: 'Select product fields to return',
                },
                // Order: Get - Blind Detail Fields
                {
                    displayName: 'Blind Detail Fields',
                    name: 'blindDetailFieldsGet',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Blind Name', value: 'blind_name' },
                        { name: 'Blind Company', value: 'blind_company' },
                        { name: 'Blind Street Address', value: 'blind_street_address' },
                        { name: 'Blind Suburb', value: 'blind_suburb' },
                        { name: 'Blind City', value: 'blind_city' },
                        { name: 'Blind Postcode', value: 'blind_postcode' },
                        { name: 'Blind State', value: 'blind_state' },
                        { name: 'Blind State Code', value: 'blind_state_code' },
                        { name: 'Blind Country', value: 'blind_country' },
                    ],
                    default: [
                        'blind_name',
                        'blind_company',
                        'blind_street_address',
                        'blind_city',
                        'blind_state',
                        'blind_country',
                    ],
                    description: 'Select blind detail fields to return',
                },
                // Order: Get - Delivery Detail Fields
                {
                    displayName: 'Delivery Detail Fields',
                    name: 'deliveryDetailFieldsGet',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Delivery Name', value: 'delivery_name' },
                        { name: 'Delivery Company', value: 'delivery_company' },
                        { name: 'Delivery Street Address', value: 'delivery_street_address' },
                        { name: 'Delivery Suburb', value: 'delivery_suburb' },
                        { name: 'Delivery City', value: 'delivery_city' },
                        { name: 'Delivery Postcode', value: 'delivery_postcode' },
                        { name: 'Delivery State', value: 'delivery_state' },
                        { name: 'Delivery State Code', value: 'delivery_state_code' },
                        { name: 'Delivery Country', value: 'delivery_country' },
                        { name: 'Delivery Telephone', value: 'delivery_telephone' },
                        { name: 'Delivery Extrafield', value: 'delivery_extrafield' },
                    ],
                    default: [
                        'delivery_name',
                        'delivery_company',
                        'delivery_street_address',
                        'delivery_city',
                        'delivery_state',
                        'delivery_country',
                        'delivery_telephone',
                    ],
                    description: 'Select delivery detail fields to return',
                },
                // Order: Get - Billing Detail Fields
                {
                    displayName: 'Billing Detail Fields',
                    name: 'billingDetailFieldsGet',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Billing Name', value: 'billing_name' },
                        { name: 'Billing Company', value: 'billing_company' },
                        { name: 'Billing Street Address', value: 'billing_street_address' },
                        { name: 'Billing Suburb', value: 'billing_suburb' },
                        { name: 'Billing City', value: 'billing_city' },
                        { name: 'Billing Postcode', value: 'billing_postcode' },
                        { name: 'Billing State', value: 'billing_state' },
                        { name: 'Billing State Code', value: 'billing_state_code' },
                        { name: 'Billing Country', value: 'billing_country' },
                        { name: 'Billing Telephone', value: 'billing_telephone' },
                        { name: 'Billing Extrafield', value: 'billing_extrafield' },
                    ],
                    default: [
                        'billing_name',
                        'billing_company',
                        'billing_street_address',
                        'billing_city',
                        'billing_state',
                        'billing_country',
                        'billing_telephone',
                    ],
                    description: 'Select billing detail fields to return',
                },
                // Order: Get - Shipment Detail Fields
                {
                    displayName: 'Shipment Detail Fields',
                    name: 'shipmentDetailFieldsGet',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['get'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Shipment Shipping Type ID', value: 'shipment_shipping_type_id' },
                        { name: 'Shipment Tracking Number', value: 'shipment_tracking_number' },
                        { name: 'Shipment Company', value: 'shipment_company' },
                        { name: 'Shipment Total Weight', value: 'shipment_total_weight' },
                        { name: 'Shipment Package', value: 'shipment_package' },
                    ],
                    default: [
                        'shipment_tracking_number',
                        'shipment_company',
                        'shipment_total_weight',
                    ],
                    description: 'Select shipment detail fields to return',
                },
                // Order: Get Many - Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPages',
                    type: 'boolean',
                    default: false,
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)',
                },
                // Order: Get Many - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParameters',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Orders ID',
                            name: 'orders_id',
                            type: 'number',
                            default: 0,
                            description: 'Filter by specific order ID',
                        },
                        {
                            displayName: 'Orders Products ID',
                            name: 'orders_products_id',
                            type: 'number',
                            default: 0,
                            description: 'Filter by orders products ID',
                        },
                        {
                            displayName: 'Order Product Status',
                            name: 'order_product_status',
                            type: 'number',
                            default: 0,
                            description: 'Filter by order product status',
                        },
                        {
                            displayName: 'Store ID',
                            name: 'store_id',
                            type: 'string',
                            default: '',
                            description: 'Filter by store ID',
                        },
                        {
                            displayName: 'From Date',
                            name: 'from_date',
                            type: 'dateTime',
                            default: '',
                            description: 'Filter orders from this date',
                        },
                        {
                            displayName: 'To Date',
                            name: 'to_date',
                            type: 'dateTime',
                            default: '',
                            description: 'Filter orders to this date',
                        },
                        {
                            displayName: 'Order Status',
                            name: 'order_status',
                            type: 'string',
                            default: '',
                            description: 'Filter by order status',
                        },
                        {
                            displayName: 'Customer ID',
                            name: 'customer_id',
                            type: 'number',
                            default: 0,
                            description: 'Filter by customer ID',
                        },
                        {
                            displayName: 'Order Type',
                            name: 'order_type',
                            type: 'options',
                            options: [
                                { name: 'All', value: '' },
                                { name: 'Standard', value: 'STANDARD' },
                                { name: 'Quote', value: 'QUOTE' },
                            ],
                            default: '',
                            description: 'Filter by order type',
                        },
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of orders to return per page (max 250). Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of orders to skip. Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Page Size',
                            name: 'pageSize',
                            type: 'number',
                            typeOptions: {
                                minValue: 1,
                                maxValue: 250,
                            },
                            default: 250,
                            description: 'Records per page when "Fetch All Pages" is enabled (max 250). Ignored for single page requests.',
                        },
                        {
                            displayName: 'Delay Between Pages (ms)',
                            name: 'pageDelay',
                            type: 'number',
                            typeOptions: {
                                minValue: 50,
                            },
                            default: 100,
                            description: 'Delay between API calls when "Fetch All Pages" is enabled (recommended: 100-500ms). Ignored for single page requests.',
                        },
                    ],
                },
                // Order: Get Many - Fields Selection (excluding Order ID)
                {
                    displayName: 'Order Fields',
                    name: 'orderFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'User ID', value: 'user_id' },
                        { name: 'Orders ID', value: 'orders_id' },
                        { name: 'Corporate ID', value: 'corporate_id' },
                        { name: 'Order Status', value: 'order_status' },
                        { name: 'Orders Status ID', value: 'orders_status_id' },
                        { name: 'Orders Date Finished', value: 'orders_date_finished' },
                        { name: 'Local Orders Date Finished', value: 'local_orders_date_finished' },
                        { name: 'Shipping Mode', value: 'shipping_mode' },
                        { name: 'Courier Company Name', value: 'courirer_company_name' },
                        { name: 'Airway Bill Number', value: 'airway_bill_number' },
                        { name: 'Payment Method Name', value: 'payment_method_name' },
                        { name: 'Total Amount', value: 'total_amount' },
                        { name: 'Order Amount', value: 'order_amount' },
                        { name: 'Shipping Amount', value: 'shipping_amount' },
                        { name: 'Tax Amount', value: 'tax_amount' },
                        { name: 'Coupon Amount', value: 'coupon_amount' },
                        { name: 'Coupon Code', value: 'coupon_code' },
                        { name: 'Coupon Type', value: 'coupon_type' },
                        { name: 'Order Vendor Amount', value: 'order_vendor_amount' },
                        { name: 'Orders Due Date', value: 'orders_due_date' },
                        { name: 'Order Last Modified Date', value: 'order_last_modified_date' },
                        { name: 'Department ID', value: 'department_id' },
                        { name: 'Cost Center Code', value: 'cost_center_code' },
                        { name: 'PO Number', value: 'po_number' },
                        { name: 'Total Weight', value: 'total_weight' },
                        { name: 'Partial Payment Details', value: 'partial_payment_details' },
                        { name: 'Refund Amount', value: 'refund_amount' },
                        { name: 'Blind Shipping Charge', value: 'blind_shipping_charge' },
                        { name: 'Payment Due Date', value: 'payment_due_date' },
                        { name: 'Transaction ID', value: 'transactionid' },
                        { name: 'Sales Agent Name', value: 'sales_agent_name' },
                        { name: 'Branch Name', value: 'branch_name' },
                        { name: 'Payment Status Title', value: 'payment_status_title' },
                        { name: 'Production Due Date', value: 'production_due_date' },
                        { name: 'Payment Processing Fees', value: 'payment_processing_fees' },
                        { name: 'Payment Date', value: 'payment_date' },
                        { name: 'Shipping Type ID', value: 'shipping_type_id' },
                        { name: 'Invoice Number', value: 'invoice_number' },
                        { name: 'Invoice Date', value: 'invoice_date' },
                        { name: 'Parent Corporate ID', value: 'parent_corporate_id' },
                        { name: 'Order Name', value: 'order_name' },
                        { name: 'Orders Extrafield', value: 'orders_extrafield' },
                        { name: 'Reviewers', value: 'reviewers' },
                        { name: 'Extrafield', value: 'extrafield' },
                    ],
                    default: [
                        'user_id',
                        'orders_id',
                        'corporate_id',
                        'order_status',
                        'orders_status_id',
                        'orders_date_finished',
                        'local_orders_date_finished',
                        'shipping_mode',
                        'courirer_company_name',
                        'airway_bill_number',
                        'payment_method_name',
                        'total_amount',
                        'order_amount',
                        'shipping_amount',
                        'tax_amount',
                        'coupon_amount',
                        'coupon_code',
                        'coupon_type',
                        'order_vendor_amount',
                        'orders_due_date',
                        'order_last_modified_date',
                        'department_id',
                        'cost_center_code',
                        'po_number',
                        'total_weight',
                        'partial_payment_details',
                        'refund_amount',
                        'blind_shipping_charge',
                        'payment_due_date',
                        'transactionid',
                        'sales_agent_name',
                        'branch_name',
                        'payment_status_title',
                        'production_due_date',
                        'payment_processing_fees',
                        'payment_date',
                        'shipping_type_id',
                        'invoice_number',
                        'invoice_date',
                        'parent_corporate_id',
                        'order_name',
                        'orders_extrafield',
                        'reviewers',
                        'extrafield',
                    ],
                    description: 'Select order fields to return',
                },
                // Order: Get Many - Customer Fields Selection
                {
                    displayName: 'Customer Fields',
                    name: 'customerFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Customers Name', value: 'customers_name' },
                        { name: 'Customers Email Address', value: 'customers_email_address' },
                        { name: 'Customers Telephone', value: 'customers_telephone' },
                        { name: 'Customers Company', value: 'customers_company' },
                        { name: 'Customers Register Date', value: 'customers_register_date' },
                        { name: 'Customers Username', value: 'customers_username' },
                        { name: 'Customers User Group Name', value: 'customers_user_group_name' },
                        { name: 'Customers Department Name', value: 'customers_department_name' },
                        { name: 'Customers Balance Amount', value: 'customers_balance_amount' },
                        { name: 'Customers Pay Limit', value: 'customers_pay_limit' },
                        { name: 'Customers Payon Enable', value: 'customers_payon_enable' },
                        { name: 'Customers Status', value: 'customers_status' },
                        { name: 'Customers First Name', value: 'customers_first_name' },
                        { name: 'Customers Last Name', value: 'customers_last_name' },
                    ],
                    default: [
                        'customers_name',
                        'customers_email_address',
                        'customers_telephone',
                        'customers_company',
                        'customers_register_date',
                        'customers_username',
                        'customers_user_group_name',
                        'customers_department_name',
                        'customers_balance_amount',
                        'customers_pay_limit',
                        'customers_payon_enable',
                        'customers_status',
                        'customers_first_name',
                        'customers_last_name',
                    ],
                    description: 'Select customer fields to return',
                },
                // Order: Get Many - Product Fields Selection
                {
                    displayName: 'Product Fields',
                    name: 'productFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Orders Products ID', value: 'orders_products_id' },
                        { name: 'Product Size Details', value: 'product_size_details' },
                        { name: 'Products Name', value: 'products_name' },
                        { name: 'Products Title', value: 'products_title' },
                        { name: 'Products SKU', value: 'products_sku' },
                        { name: 'Products Price', value: 'products_price' },
                        { name: 'Products Quantity', value: 'products_quantity' },
                        { name: 'Template Type', value: 'template_type' },
                        { name: 'Features Details', value: 'features_details' },
                        { name: 'Photo Print Details', value: 'photo_print_details' },
                        { name: 'Product Size', value: 'productsize' },
                        { name: 'Mass Personalization Files', value: 'mass_personalization_files' },
                        { name: 'Products Vendor Price', value: 'products_vendor_price' },
                        { name: 'Products Weight', value: 'products_weight' },
                        { name: 'Inventory Storage Days', value: 'inventory_storage_days' },
                        { name: 'Product Status ID', value: 'product_status_id' },
                        { name: 'Product Status', value: 'product_status' },
                        { name: 'Product ID', value: 'product_id' },
                        { name: 'Reference Order ID', value: 'reference_order_id' },
                        { name: 'Is Kit', value: 'is_kit' },
                        { name: 'Product Tax', value: 'product_tax' },
                        { name: 'Product Info', value: 'product_info' },
                        { name: 'Template Info', value: 'template_info' },
                        { name: 'Product Printer Name', value: 'product_printer_name' },
                        { name: 'Products Unit Price', value: 'products_unit_price' },
                        { name: 'Quote ID', value: 'quote_id' },
                        { name: 'Product Production Due Date', value: 'product_production_due_date' },
                        { name: 'Orders Products ID Pattern', value: 'orders_products_id_pattern' },
                        { name: 'Orders Products Last Modified Date', value: 'orders_products_last_modified_date' },
                        { name: 'Predefined Product Type', value: 'predefined_product_type' },
                        { name: 'Ziflow Link', value: 'ziflow_link' },
                        { name: 'Print Ready Files', value: 'print_ready_files' },
                        { name: 'Proof Files', value: 'proof_files' },
                        { name: 'Item Extra Info JSON', value: 'item_extra_info_json' },
                    ],
                    default: [
                        'orders_products_id',
                        'product_size_details',
                        'products_name',
                        'products_title',
                        'products_sku',
                        'products_price',
                        'products_quantity',
                        'template_type',
                        'features_details',
                        'photo_print_details',
                        'productsize',
                        'mass_personalization_files',
                        'products_vendor_price',
                        'products_weight',
                        'inventory_storage_days',
                        'product_status_id',
                        'product_status',
                        'product_id',
                        'reference_order_id',
                        'is_kit',
                        'product_tax',
                        'product_info',
                        'template_info',
                        'product_printer_name',
                        'products_unit_price',
                        'quote_id',
                        'product_production_due_date',
                        'orders_products_id_pattern',
                        'orders_products_last_modified_date',
                        'predefined_product_type',
                        'ziflow_link',
                        'print_ready_files',
                        'proof_files',
                        'item_extra_info_json',
                    ],
                    description: 'Select product fields to return',
                },
                // Order: Get Many - Blind Detail Fields Selection
                {
                    displayName: 'Blind Detail Fields',
                    name: 'blindDetailFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Blind Name', value: 'blind_name' },
                        { name: 'Blind Company', value: 'blind_company' },
                        { name: 'Blind Street Address', value: 'blind_street_address' },
                        { name: 'Blind Suburb', value: 'blind_suburb' },
                        { name: 'Blind City', value: 'blind_city' },
                        { name: 'Blind Postcode', value: 'blind_postcode' },
                        { name: 'Blind State', value: 'blind_state' },
                        { name: 'Blind State Code', value: 'blind_state_code' },
                        { name: 'Blind Country', value: 'blind_country' },
                    ],
                    default: [
                        'blind_name',
                        'blind_company',
                        'blind_street_address',
                        'blind_suburb',
                        'blind_city',
                        'blind_postcode',
                        'blind_state',
                        'blind_state_code',
                        'blind_country',
                    ],
                    description: 'Select blind detail fields to return',
                },
                // Order: Get Many - Delivery Detail Fields Selection
                {
                    displayName: 'Delivery Detail Fields',
                    name: 'deliveryDetailFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Delivery Name', value: 'delivery_name' },
                        { name: 'Delivery Company', value: 'delivery_company' },
                        { name: 'Delivery Street Address', value: 'delivery_street_address' },
                        { name: 'Delivery Suburb', value: 'delivery_suburb' },
                        { name: 'Delivery City', value: 'delivery_city' },
                        { name: 'Delivery Postcode', value: 'delivery_postcode' },
                        { name: 'Delivery State', value: 'delivery_state' },
                        { name: 'Delivery State Code', value: 'delivery_state_code' },
                        { name: 'Delivery Country', value: 'delivery_country' },
                        { name: 'Delivery Telephone', value: 'delivery_telephone' },
                        { name: 'Delivery Extrafield', value: 'delivery_extrafield' },
                    ],
                    default: [
                        'delivery_name',
                        'delivery_company',
                        'delivery_street_address',
                        'delivery_suburb',
                        'delivery_city',
                        'delivery_postcode',
                        'delivery_state',
                        'delivery_state_code',
                        'delivery_country',
                        'delivery_telephone',
                        'delivery_extrafield',
                    ],
                    description: 'Select delivery detail fields to return',
                },
                // Order: Get Many - Billing Detail Fields Selection
                {
                    displayName: 'Billing Detail Fields',
                    name: 'billingDetailFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Billing Name', value: 'billing_name' },
                        { name: 'Billing Company', value: 'billing_company' },
                        { name: 'Billing Street Address', value: 'billing_street_address' },
                        { name: 'Billing Suburb', value: 'billing_suburb' },
                        { name: 'Billing City', value: 'billing_city' },
                        { name: 'Billing Postcode', value: 'billing_postcode' },
                        { name: 'Billing State', value: 'billing_state' },
                        { name: 'Billing State Code', value: 'billing_state_code' },
                        { name: 'Billing Country', value: 'billing_country' },
                        { name: 'Billing Telephone', value: 'billing_telephone' },
                        { name: 'Billing Extrafield', value: 'billing_extrafield' },
                    ],
                    default: [
                        'billing_name',
                        'billing_company',
                        'billing_street_address',
                        'billing_suburb',
                        'billing_city',
                        'billing_postcode',
                        'billing_state',
                        'billing_state_code',
                        'billing_country',
                        'billing_telephone',
                        'billing_extrafield',
                    ],
                    description: 'Select billing detail fields to return',
                },
                // Order: Get Many - Shipment Detail Fields Selection
                {
                    displayName: 'Shipment Detail Fields',
                    name: 'shipmentDetailFieldsGetAll',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Shipment Shipping Type ID', value: 'shipment_shipping_type_id' },
                        { name: 'Shipment Tracking Number', value: 'shipment_tracking_number' },
                        { name: 'Shipment Company', value: 'shipment_company' },
                        { name: 'Shipment Total Weight', value: 'shipment_total_weight' },
                        { name: 'Shipment Package', value: 'shipment_package' },
                    ],
                    default: [
                        'shipment_shipping_type_id',
                        'shipment_tracking_number',
                        'shipment_company',
                        'shipment_total_weight',
                        'shipment_package',
                    ],
                    description: 'Select shipment detail fields to return',
                },
                // Order: Get Shipments - Order ID Field
                {
                    displayName: 'Order ID',
                    name: 'orderIdShipments',
                    type: 'number',
                    required: true,
                    default: 0,
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getShipments'],
                        },
                    },
                    description: 'ID of the order to retrieve shipment details for',
                },
                // Order: Get Shipments - Fields Selection
                {
                    displayName: 'Shipment Fields',
                    name: 'shipmentFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['getShipments'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Tracking Number', value: 'shipment_tracking_number' },
                        { name: 'Company', value: 'shipment_company' },
                        { name: 'Total Weight', value: 'shipment_total_weight' },
                        { name: 'Package', value: 'shipment_package' },
                    ],
                    default: [
                        'shipment_tracking_number',
                        'shipment_company',
                        'shipment_total_weight',
                        'shipment_package',
                    ],
                    description: 'Select shipment fields to return',
                },
                // Order: Create Shipment - Order ID Field
                {
                    displayName: 'Order ID',
                    name: 'orderIdCreate',
                    type: 'number',
                    required: true,
                    default: 0,
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['createShipment'],
                        },
                    },
                    description: 'ID of the order to create shipment for',
                },
                // Order: Create Shipment - Shipment ID Field
                {
                    displayName: 'Shipment ID',
                    name: 'shipmentId',
                    type: 'number',
                    required: false,
                    default: 0,
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['createShipment'],
                        },
                    },
                    description: 'Shipment ID (optional, leave 0 for new shipment)',
                },
                // Order: Create Shipment - Tracking Number
                {
                    displayName: 'Tracking Number',
                    name: 'trackingNumber',
                    type: 'string',
                    required: false,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['createShipment'],
                        },
                    },
                    description: 'Tracking number for the shipment',
                },
                // Order: Create Shipment - Packages
                {
                    displayName: 'Packages',
                    name: 'packages',
                    type: 'fixedCollection',
                    typeOptions: {
                        multipleValues: true,
                    },
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['order'],
                            operation: ['createShipment'],
                        },
                    },
                    placeholder: 'Add Package',
                    options: [
                        {
                            displayName: 'Package',
                            name: 'package',
                            values: [
                                {
                                    displayName: 'Weight',
                                    name: 'weight',
                                    type: 'number',
                                    default: 0,
                                    description: 'Package weight',
                                },
                                {
                                    displayName: 'Length',
                                    name: 'length',
                                    type: 'number',
                                    default: 0,
                                    description: 'Package length',
                                },
                                {
                                    displayName: 'Width',
                                    name: 'width',
                                    type: 'number',
                                    default: 0,
                                    description: 'Package width',
                                },
                                {
                                    displayName: 'Height',
                                    name: 'height',
                                    type: 'number',
                                    default: 0,
                                    description: 'Package height',
                                },
                                {
                                    displayName: 'Package Tracking',
                                    name: 'tracking',
                                    type: 'string',
                                    default: '',
                                    description: 'Package tracking number',
                                },
                                {
                                    displayName: 'Order Products',
                                    name: 'orderProducts',
                                    type: 'fixedCollection',
                                    typeOptions: {
                                        multipleValues: true,
                                    },
                                    placeholder: 'Add Product',
                                    default: {},
                                    options: [
                                        {
                                            displayName: 'Product',
                                            name: 'product',
                                            values: [
                                                {
                                                    displayName: 'Product ID',
                                                    name: 'opid',
                                                    type: 'number',
                                                    default: 0,
                                                    description: 'Order product ID',
                                                },
                                                {
                                                    displayName: 'Quantity',
                                                    name: 'qty',
                                                    type: 'string',
                                                    default: '1',
                                                    description: 'Quantity for this product',
                                                },
                                            ],
                                        },
                                    ],
                                    description: 'Order products included in this package',
                                },
                            ],
                        },
                    ],
                    description: 'Package information for the shipment (can add multiple packages)',
                },
                // Product Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: {
                        show: {
                            resource: ['product'],
                        },
                    },
                    options: [
                        {
                            name: 'Get Simple',
                            value: 'getSimple',
                            description: 'Get a single product with simple fields',
                            action: 'Get a product (simple)',
                        },
                        {
                            name: 'Get Many Simple',
                            value: 'getManySimple',
                            description: 'Get many products with simple fields',
                            action: 'Get many products (simple)',
                        },
                        {
                            name: 'Get Detailed',
                            value: 'getDetailed',
                            description: 'Get a single product with detailed fields',
                            action: 'Get a product (detailed)',
                        },
                        {
                            name: 'Get Many Detailed',
                            value: 'getManyDetailed',
                            description: 'Get many products with detailed fields',
                            action: 'Get many products (detailed)',
                        },
                        {
                            name: 'Get Master Options',
                            value: 'getMasterOptions',
                            description: 'Get master options for a product',
                            action: 'Get product master options',
                        },
                        {
                            name: 'Get Many Master Options',
                            value: 'getManyMasterOptions',
                            description: 'Get master options for many products',
                            action: 'Get many product master options',
                        },
                        {
                            name: 'Get Options Rules',
                            value: 'getOptionsRules',
                            description: 'Get options rules for a product',
                            action: 'Get product options rules',
                        },
                        {
                            name: 'Get Many Options Rules',
                            value: 'getManyOptionsRules',
                            description: 'Get options rules for many products',
                            action: 'Get many product options rules',
                        },
                        {
                            name: 'Get Master Option Tag',
                            value: 'getMasterOptionTag',
                            description: 'Get master option tags',
                            action: 'Get master option tags',
                        },
                        {
                            name: 'Get Option Group',
                            value: 'getOptionGroup',
                            description: 'Get option groups',
                            action: 'Get option groups',
                        },
                        {
                            name: 'Get Option Formulas',
                            value: 'getCustomFormula',
                            description: 'Get custom formulas',
                            action: 'Get custom formulas',
                        },
                        {
                            name: 'Get Master Option Ranges',
                            value: 'getMasterOptionRange',
                            description: 'Get master option ranges',
                            action: 'Get master option ranges',
                        },
                        {
                            name: 'Get FAQ Categories',
                            value: 'get_faq_category',
                            description: 'Get FAQ categories',
                            action: 'Get FAQ categories',
                        },
                        {
                            name: 'Get Additional Options (Staging)',
                            value: 'product_additional_options',
                            description: 'Get product additional options (staging)',
                            action: 'Get product additional options',
                        },
                        {
                            name: 'Get Attribute Prices (Staging)',
                            value: 'products_attribute_price',
                            description: 'Get product attribute prices (staging)',
                            action: 'Get product attribute prices',
                        },
                        {
                            name: 'Get Prices',
                            value: 'getPrices',
                            description: 'Get prices for a product',
                            action: 'Get product prices',
                        },
                        {
                            name: 'Get Many Prices',
                            value: 'getManyPrices',
                            description: 'Get prices for many products',
                            action: 'Get many product prices',
                        },
                        {
                            name: 'Get Option Prices',
                            value: 'getOptionPrices',
                            description: 'Get option prices for a product',
                            action: 'Get product option prices',
                        },
                        {
                            name: 'Get Many Option Prices',
                            value: 'getManyOptionPrices',
                            description: 'Get option prices for many products',
                            action: 'Get many product option prices',
                        },
                        {
                            name: 'Get Category',
                            value: 'getCategory',
                            description: 'Get a single product category',
                            action: 'Get a product category',
                        },
                        {
                            name: 'Get Many Categories',
                            value: 'getManyCategories',
                            description: 'Get many product categories',
                            action: 'Get many product categories',
                        },
                        {
                            name: 'Get FAQs',
                            value: 'getFAQs',
                            description: 'Get FAQs for a product or category',
                            action: 'Get FAQs',
                        },
                        {
                            name: 'Get Many FAQs',
                            value: 'getManyFAQs',
                            description: 'Get many FAQs',
                            action: 'Get many FAQs',
                        },
                        {
                            name: 'Get Stock',
                            value: 'getStock',
                            description: 'Get product stock information',
                            action: 'Get product stock',
                        },
                        {
                            name: 'Update Stock',
                            value: 'updateStock',
                            description: 'Update product stock',
                            action: 'Update product stock',
                        },
                    ],
                    default: 'getSimple',
                },
                // Product: Master Option Tag (getMasterOptionTag)
                {
                    displayName: 'Master Option Tag ID',
                    name: 'masterOptionTag_master_option_tag_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getMasterOptionTag'] } },
                    default: 0,
                    description: 'Filter by master option tag ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'masterOptionTag_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getMasterOptionTag'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'masterOptionTag_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getMasterOptionTag'] } },
                    default: 0,
                },
                // Product: Option Group (getOptionGroup)
                {
                    displayName: 'Product Additional Option Group ID',
                    name: 'optionGroup_prod_add_opt_group_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getOptionGroup'] } },
                    default: 0,
                    description: 'Filter by product additional option group ID (0 = no filter)',
                },
                {
                    displayName: 'Use For',
                    name: 'optionGroup_use_for',
                    type: 'string',
                    displayOptions: { show: { resource: ['product'], operation: ['getOptionGroup'] } },
                    default: '',
                    description: 'Filter by use_for (optional)',
                },
                {
                    displayName: 'Limit',
                    name: 'optionGroup_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getOptionGroup'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'optionGroup_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getOptionGroup'] } },
                    default: 0,
                },
                // Product: Option Formulas (getCustomFormula)
                {
                    displayName: 'Formula ID',
                    name: 'customFormula_formula_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getCustomFormula'] } },
                    default: 0,
                    description: 'Filter by formula ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'customFormula_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getCustomFormula'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'customFormula_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getCustomFormula'] } },
                    default: 0,
                },
                // Product: Master Option Ranges (getMasterOptionRange)
                {
                    displayName: 'Range ID',
                    name: 'masterOptionRange_range_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getMasterOptionRange'] } },
                    default: 0,
                    description: 'Filter by range ID (0 = no filter)',
                },
                {
                    displayName: 'Option ID',
                    name: 'masterOptionRange_option_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getMasterOptionRange'] } },
                    default: 0,
                    description: 'Filter by option ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'masterOptionRange_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getMasterOptionRange'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'masterOptionRange_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['getMasterOptionRange'] } },
                    default: 0,
                },
                // Product: FAQ Category (get_faq_category)
                {
                    displayName: 'FAQ Category ID',
                    name: 'faqCategory_faqcat_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['get_faq_category'] } },
                    default: 0,
                    description: 'Filter by FAQ category ID (0 = no filter)',
                },
                {
                    displayName: 'Status',
                    name: 'faqCategory_status',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['get_faq_category'] } },
                    default: 0,
                    description: 'Filter by status (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'faqCategory_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['get_faq_category'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'faqCategory_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['get_faq_category'] } },
                    default: 0,
                },
                // Product: Additional Options (product_additional_options) — Staging
                {
                    displayName: 'Products ID',
                    name: 'additionalOptions_products_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['product_additional_options'] } },
                    default: 0,
                    description: 'Filter by products ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'additionalOptions_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['product_additional_options'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'additionalOptions_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['product_additional_options'] } },
                    default: 0,
                },
                // Product: Attribute Price (products_attribute_price) — Staging
                {
                    displayName: 'Attribute ID',
                    name: 'attributePrice_attribute_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['products_attribute_price'] } },
                    default: 0,
                    description: 'Filter by attribute ID (0 = no filter)',
                },
                {
                    displayName: 'Size ID',
                    name: 'attributePrice_size_id',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['products_attribute_price'] } },
                    default: 0,
                    description: 'Filter by size ID (0 = no filter)',
                },
                {
                    displayName: 'Limit',
                    name: 'attributePrice_limit',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['products_attribute_price'] } },
                    default: 10,
                },
                {
                    displayName: 'Offset',
                    name: 'attributePrice_offset',
                    type: 'number',
                    displayOptions: { show: { resource: ['product'], operation: ['products_attribute_price'] } },
                    default: 0,
                },
                // Product: Get Simple - Product ID
                {
                    displayName: 'Product ID',
                    name: 'productId',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getSimple'],
                        },
                    },
                    description: 'ID of the product to retrieve',
                },
                // Product: Get Simple - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParameters',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getSimple'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of products to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of products to skip',
                        },
                    ],
                },
                // Product: Get Simple - Fields Selection
                {
                    displayName: 'Product Fields',
                    name: 'productFieldsSimple',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getSimple'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Product ID', value: 'product_id' },
                        { name: 'Product Name', value: 'product_name' },
                        { name: 'Main SKU', value: 'main_sku' },
                        { name: 'Is Stock', value: 'isstock' },
                    ],
                    default: [
                        'product_id',
                        'product_name',
                        'main_sku',
                        'isstock',
                    ],
                    description: 'Select product fields to return',
                },
                // Product: Get Many Simple - Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPages',
                    type: 'boolean',
                    default: false,
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManySimple'],
                        },
                    },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)',
                },
                // Product: Get Many Simple - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManySimple',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManySimple'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of products to return per page (max 250). Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of products to skip. Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Page Size',
                            name: 'pageSize',
                            type: 'number',
                            typeOptions: {
                                minValue: 1,
                                maxValue: 250,
                            },
                            default: 250,
                            description: 'Records per page when "Fetch All Pages" is enabled (max 250 - API hard limit). Ignored for single page requests.',
                        },
                        {
                            displayName: 'Delay Between Pages (ms)',
                            name: 'pageDelay',
                            type: 'number',
                            typeOptions: {
                                minValue: 25,
                            },
                            default: 50,
                            description: 'Delay between API calls when "Fetch All Pages" is enabled (default 50ms for better performance, min 25ms). Ignored for single page requests.',
                        },
                    ],
                },
                // Product: Get Many Simple - Fields Selection
                {
                    displayName: 'Product Fields',
                    name: 'productFieldsManySimple',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManySimple'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Product ID', value: 'product_id' },
                        { name: 'Product Name', value: 'product_name' },
                        { name: 'Main SKU', value: 'main_sku' },
                        { name: 'Is Stock', value: 'isstock' },
                    ],
                    default: [
                        'product_id',
                        'product_name',
                        'main_sku',
                        'isstock',
                    ],
                    description: 'Select product fields to return',
                },
                // Product: Get Detailed - Product ID
                {
                    displayName: 'Product ID',
                    name: 'productIdDetailed',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getDetailed'],
                        },
                    },
                    description: 'ID of the product to retrieve',
                },
                // Product: Get Detailed - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersDetailed',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getDetailed'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of products to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of products to skip',
                        },
                        {
                            displayName: 'Status',
                            name: 'status',
                            type: 'number',
                            default: 1,
                            description: 'Product status filter',
                        },
                        {
                            displayName: 'All Store',
                            name: 'all_store',
                            type: 'number',
                            default: 0,
                            description: 'All store filter',
                        },
                        {
                            displayName: 'External Catalogue',
                            name: 'externalCatalogue',
                            type: 'number',
                            default: 0,
                            description: 'Filter by external catalogue (0 or 1)',
                        },
                    ],
                },
                // Product: Get Detailed - Fields Selection
                {
                    displayName: 'Product Fields',
                    name: 'productFieldsDetailed',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getDetailed'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Product ID', value: 'product_id' },
                        { name: 'Status', value: 'status' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Product Name', value: 'product_name' },
                        { name: 'Kit Type ID', value: 'kit_type_id' },
                        { name: 'Kit Products', value: 'kit_products' },
                        { name: 'Associate Option ID', value: 'associate_option_id' },
                        { name: 'Associate Option Key', value: 'associate_option_key' },
                        { name: 'Associate Attribute ID', value: 'associate_attribute_id' },
                        { name: 'Associate Attribute Key', value: 'associate_attribute_key' },
                        { name: 'Associate Size ID', value: 'associate_size_id' },
                        { name: 'Associate Multiplier', value: 'associate_multiplier' },
                        { name: 'Associate Status', value: 'associate_status' },
                        { name: 'Associate Calculation Type', value: 'associate_calculation_type' },
                        { name: 'Default Category ID', value: 'default_category_id' },
                        { name: 'Associated Category IDs', value: 'associated_category_ids' },
                        { name: 'Default Category Name', value: 'default_category_name' },
                        { name: 'Associated Category Names', value: 'associated_category_names' },
                        { name: 'Small Image', value: 'small_image' },
                        { name: 'Large Image', value: 'large_image' },
                        { name: 'Product URL', value: 'product_url' },
                        { name: 'Long Description', value: 'long_description' },
                        { name: 'Predefined Product Type', value: 'predefined_product_type' },
                        { name: 'All Store', value: 'all_store' },
                        { name: 'Products Internal Name', value: 'products_internal_name' },
                        { name: 'Search Keywords', value: 'search_keywords' },
                        { name: 'Short Description', value: 'short_description' },
                        { name: 'Long Description Two', value: 'long_description_two' },
                        { name: 'SEO Page Title', value: 'seo_page_title' },
                        { name: 'SEO Page Description', value: 'seo_page_description' },
                        { name: 'Schema Markup', value: 'schema_markup' },
                        { name: 'SEO Page Metatags', value: 'seo_page_metatags' },
                        { name: 'Main SKU', value: 'main_sku' },
                        { name: 'Default Production Days', value: 'default_production_days' },
                        { name: 'Product Cut Off Time', value: 'product_cut_off_time' },
                        { name: 'Products Draw Area Margins', value: 'products_draw_area_margins' },
                        { name: 'Products Draw Cutting Margins', value: 'products_draw_cutting_margins' },
                        { name: 'Product Pages', value: 'productpages' },
                        { name: 'Custom Size Restrict Data', value: 'custom_size_restrict_data' },
                        { name: 'Product Default Quantity Interval', value: 'product_default_quantity_interval' },
                        { name: 'Custom Cross Check Height Width', value: 'custom_cross_check_height_width' },
                        { name: 'Custom Size Info', value: 'custom_size_info' },
                        { name: 'Product Setup Cost', value: 'product_setup_cost' },
                        { name: 'Product Hire Designer Cost', value: 'product_hire_designer_cost' },
                        { name: 'Product Minimum Price', value: 'product_minimum_price' },
                        { name: 'Product Start Price', value: 'product_start_price' },
                        { name: 'External Catalogue', value: 'externalCatalogue' },
                    ],
                    default: [
                        'product_id',
                        'status',
                        'sort_order',
                        'product_name',
                        'default_category_id',
                        'associated_category_ids',
                        'default_category_name',
                        'associated_category_names',
                        'small_image',
                        'large_image',
                        'product_url',
                        'long_description',
                        'predefined_product_type',
                        'all_store',
                        'products_internal_name',
                        'search_keywords',
                        'short_description',
                        'long_description_two',
                        'seo_page_title',
                        'seo_page_description',
                        'schema_markup',
                        'seo_page_metatags',
                        'main_sku',
                        'default_production_days',
                        'product_cut_off_time',
                        'products_draw_area_margins',
                        'products_draw_cutting_margins',
                        'productpages',
                        'custom_size_restrict_data',
                        'product_default_quantity_interval',
                        'custom_cross_check_height_width',
                        'custom_size_info',
                        'product_setup_cost',
                        'product_hire_designer_cost',
                        'product_minimum_price',
                        'product_start_price',
                    ],
                    description: 'Select product fields to return',
                },
                // Product: Get Many Detailed - Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPages',
                    type: 'boolean',
                    default: false,
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyDetailed'],
                        },
                    },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)',
                },
                // Product: Get Many Detailed - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManyDetailed',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyDetailed'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of products to return per page (max 250). Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of products to skip. Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Page Size',
                            name: 'pageSize',
                            type: 'number',
                            typeOptions: {
                                minValue: 1,
                                maxValue: 250,
                            },
                            default: 250,
                            description: 'Records per page when "Fetch All Pages" is enabled (max 250 - API hard limit). Ignored for single page requests.',
                        },
                        {
                            displayName: 'Delay Between Pages (ms)',
                            name: 'pageDelay',
                            type: 'number',
                            typeOptions: {
                                minValue: 25,
                            },
                            default: 50,
                            description: 'Delay between API calls when "Fetch All Pages" is enabled (default 50ms for better performance, min 25ms). Ignored for single page requests.',
                        },
                        {
                            displayName: 'Status',
                            name: 'status',
                            type: 'number',
                            default: 1,
                            description: 'Product status filter',
                        },
                        {
                            displayName: 'All Store',
                            name: 'all_store',
                            type: 'number',
                            default: 0,
                            description: 'All store filter',
                        },
                        {
                            displayName: 'External Catalogue',
                            name: 'externalCatalogue',
                            type: 'number',
                            default: 0,
                            description: 'Filter by external catalogue (0 or 1)',
                        },
                    ],
                },
                // Product: Get Many Detailed - Fields Selection
                {
                    displayName: 'Product Fields',
                    name: 'productFieldsManyDetailed',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyDetailed'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Product ID', value: 'product_id' },
                        { name: 'Status', value: 'status' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Product Name', value: 'product_name' },
                        { name: 'Kit Type ID', value: 'kit_type_id' },
                        { name: 'Kit Products', value: 'kit_products' },
                        { name: 'Associate Option ID', value: 'associate_option_id' },
                        { name: 'Associate Option Key', value: 'associate_option_key' },
                        { name: 'Associate Attribute ID', value: 'associate_attribute_id' },
                        { name: 'Associate Attribute Key', value: 'associate_attribute_key' },
                        { name: 'Associate Size ID', value: 'associate_size_id' },
                        { name: 'Associate Multiplier', value: 'associate_multiplier' },
                        { name: 'Associate Status', value: 'associate_status' },
                        { name: 'Associate Calculation Type', value: 'associate_calculation_type' },
                        { name: 'Default Category ID', value: 'default_category_id' },
                        { name: 'Associated Category IDs', value: 'associated_category_ids' },
                        { name: 'Default Category Name', value: 'default_category_name' },
                        { name: 'Associated Category Names', value: 'associated_category_names' },
                        { name: 'Small Image', value: 'small_image' },
                        { name: 'Large Image', value: 'large_image' },
                        { name: 'Product URL', value: 'product_url' },
                        { name: 'Long Description', value: 'long_description' },
                        { name: 'Predefined Product Type', value: 'predefined_product_type' },
                        { name: 'All Store', value: 'all_store' },
                        { name: 'Products Internal Name', value: 'products_internal_name' },
                        { name: 'Search Keywords', value: 'search_keywords' },
                        { name: 'Short Description', value: 'short_description' },
                        { name: 'Long Description Two', value: 'long_description_two' },
                        { name: 'SEO Page Title', value: 'seo_page_title' },
                        { name: 'SEO Page Description', value: 'seo_page_description' },
                        { name: 'Schema Markup', value: 'schema_markup' },
                        { name: 'SEO Page Metatags', value: 'seo_page_metatags' },
                        { name: 'Main SKU', value: 'main_sku' },
                        { name: 'Default Production Days', value: 'default_production_days' },
                        { name: 'Product Cut Off Time', value: 'product_cut_off_time' },
                        { name: 'Products Draw Area Margins', value: 'products_draw_area_margins' },
                        { name: 'Products Draw Cutting Margins', value: 'products_draw_cutting_margins' },
                        { name: 'Product Pages', value: 'productpages' },
                        { name: 'Custom Size Restrict Data', value: 'custom_size_restrict_data' },
                        { name: 'Product Default Quantity Interval', value: 'product_default_quantity_interval' },
                        { name: 'Custom Cross Check Height Width', value: 'custom_cross_check_height_width' },
                        { name: 'Custom Size Info', value: 'custom_size_info' },
                        { name: 'Product Setup Cost', value: 'product_setup_cost' },
                        { name: 'Product Hire Designer Cost', value: 'product_hire_designer_cost' },
                        { name: 'Product Minimum Price', value: 'product_minimum_price' },
                        { name: 'Product Start Price', value: 'product_start_price' },
                        { name: 'External Catalogue', value: 'externalCatalogue' },
                        { name: '─────────────────────────────', value: 'SEPARATOR2' },
                        { name: 'Product Size (nested)', value: 'product_size' },
                        { name: 'Product Additional Options (nested)', value: 'product_additional_options' },
                    ], default: [
                        'product_id',
                        'status',
                        'sort_order',
                        'product_name',
                        'default_category_id',
                        'associated_category_ids',
                        'default_category_name',
                        'associated_category_names',
                        'small_image',
                        'large_image',
                        'product_url',
                        'long_description',
                        'predefined_product_type',
                        'all_store',
                        'products_internal_name',
                        'search_keywords',
                        'short_description',
                        'long_description_two',
                        'seo_page_title',
                        'seo_page_description',
                        'schema_markup',
                        'seo_page_metatags',
                        'main_sku',
                        'default_production_days',
                        'product_cut_off_time',
                        'products_draw_area_margins',
                        'products_draw_cutting_margins',
                        'productpages',
                        'custom_size_restrict_data',
                        'product_default_quantity_interval',
                        'custom_cross_check_height_width',
                        'custom_size_info',
                        'product_setup_cost',
                        'product_hire_designer_cost',
                        'product_minimum_price',
                        'product_start_price',
                    ],
                    description: 'Select product fields to return',
                },
                // Product: Get Many Detailed - Product Size Fields (Nested)
                {
                    displayName: 'Product Size Fields',
                    name: 'productSizeFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getDetailed', 'getManyDetailed'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Size Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Size Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Size ID', value: 'size_id' },
                        { name: 'Size Image', value: 'size_image' },
                        { name: 'Size Title', value: 'size_title' },
                        { name: 'Size Unit', value: 'size_unit' },
                        { name: 'Size Width', value: 'size_width' },
                        { name: 'Size Height', value: 'size_height' },
                        { name: 'Sort Order', value: 'sort_order' },
                    ],
                    default: [
                        'size_id',
                        'size_title',
                        'size_width',
                        'size_height',
                        'sort_order',
                    ],
                    description: 'Select product size fields to return. Leave empty to exclude product sizes.',
                },
                // Product: Get Many Detailed - Product Additional Options Fields (Nested)
                {
                    displayName: 'Product Additional Options Fields',
                    name: 'productAdditionalOptionsFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getDetailed', 'getManyDetailed'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Option Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Option Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Product Additional Option ID', value: 'product_additional_option_id' },
                        { name: 'Master Option ID', value: 'master_option_id' },
                        { name: 'Option Key', value: 'option_key' },
                        { name: 'Title', value: 'title' },
                        { name: 'Options Type', value: 'options_type' },
                        { name: 'Required', value: 'required' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Attributes', value: 'attributes' },
                    ],
                    default: [
                        'product_additional_option_id',
                        'master_option_id',
                        'option_key',
                        'title',
                        'options_type',
                        'required',
                        'sort_order',
                        'attributes',
                    ],
                    description: 'Select product additional options fields to return. Leave empty to exclude additional options.',
                },
                // Product: Get Category - Category ID
                {
                    displayName: 'Category ID',
                    name: 'categoryId',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getCategory'],
                        },
                    },
                    description: 'ID of the category to retrieve',
                },
                // Product: Get Category - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersCategory',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getCategory'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of categories to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of categories to skip',
                        },
                    ],
                },
                // Product: Get Category - Fields Selection
                {
                    displayName: 'Category Fields',
                    name: 'categoryFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getCategory'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Category ID', value: 'category_id' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Status', value: 'status' },
                        { name: 'Parent ID', value: 'parent_id' },
                        { name: 'Category Name', value: 'category_name' },
                        { name: 'Category URL', value: 'category_url' },
                        { name: 'Category Internal Name', value: 'category_internal_name' },
                        { name: 'Category Image', value: 'category_image' },
                        { name: 'Short Description', value: 'short_description' },
                        { name: 'Category Header Content', value: 'category_header_content' },
                        { name: 'Long Description Two', value: 'long_description_two' },
                        { name: 'Long Description', value: 'long_description' },
                        { name: 'SEO Page Title', value: 'seo_page_title' },
                        { name: 'SEO Page Description', value: 'seo_page_description' },
                        { name: 'Schema Markup', value: 'schema_markup' },
                    ],
                    default: [
                        'category_id',
                        'sort_order',
                        'status',
                        'parent_id',
                        'category_name',
                        'category_url',
                        'category_internal_name',
                        'category_image',
                        'short_description',
                        'category_header_content',
                        'long_description_two',
                        'long_description',
                        'seo_page_title',
                        'seo_page_description',
                        'schema_markup',
                    ],
                    description: 'Select category fields to return',
                },
                // Product: Get Many Categories - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManyCategories',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyCategories'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of categories to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of categories to skip',
                        },
                    ],
                },
                // Product: Get Many Categories - Fields Selection
                {
                    displayName: 'Category Fields',
                    name: 'categoryFieldsMany',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyCategories'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Category ID', value: 'category_id' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Status', value: 'status' },
                        { name: 'Parent ID', value: 'parent_id' },
                        { name: 'Category Name', value: 'category_name' },
                        { name: 'Category URL', value: 'category_url' },
                        { name: 'Category Internal Name', value: 'category_internal_name' },
                        { name: 'Category Image', value: 'category_image' },
                        { name: 'Short Description', value: 'short_description' },
                        { name: 'Category Header Content', value: 'category_header_content' },
                        { name: 'Long Description Two', value: 'long_description_two' },
                        { name: 'Long Description', value: 'long_description' },
                        { name: 'SEO Page Title', value: 'seo_page_title' },
                        { name: 'SEO Page Description', value: 'seo_page_description' },
                        { name: 'Schema Markup', value: 'schema_markup' },
                    ],
                    default: [
                        'category_id',
                        'sort_order',
                        'status',
                        'parent_id',
                        'category_name',
                        'category_url',
                        'category_internal_name',
                        'category_image',
                        'short_description',
                        'category_header_content',
                        'long_description_two',
                        'long_description',
                        'seo_page_title',
                        'seo_page_description',
                        'schema_markup',
                    ],
                    description: 'Select category fields to return',
                },
                // Product: Get Stock - Product ID
                {
                    displayName: 'Product ID',
                    name: 'productIdStock',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getStock'],
                        },
                    },
                    description: 'ID of the product to retrieve stock for',
                },
                // Product: Get Stock - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersStock',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getStock'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of stock records to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of stock records to skip',
                        },
                    ],
                },
                // Product: Get Stock - Fields Selection
                {
                    displayName: 'Stock Fields',
                    name: 'stockFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product', 'productStocks'],
                            operation: ['getStock', 'getAll'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Stock ID', value: 'stock_id' },
                        { name: 'Product ID', value: 'product_id' },
                        { name: 'Product Name', value: 'product_name' },
                        { name: 'Size ID', value: 'size_id' },
                        { name: 'Size Title', value: 'size_title' },
                        { name: 'Credit Stock', value: 'credit_stock' },
                        { name: 'Debited Stock', value: 'debited_stock' },
                        { name: 'Stock Quantity', value: 'stock_quantity' },
                        { name: 'Option Details', value: 'option_details' },
                    ],
                    default: [
                        'stock_id',
                        'product_id',
                        'product_name',
                        'size_id',
                        'size_title',
                        'credit_stock',
                        'debited_stock',
                        'stock_quantity',
                        'option_details',
                    ],
                    description: 'Select stock fields to return',
                },
                // Product: Update Stock - Identifier Type
                {
                    displayName: 'Identifier Type',
                    name: 'stockIdentifierType',
                    type: 'options',
                    required: true,
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['updateStock'],
                        },
                    },
                    options: [
                        {
                            name: 'Stock ID',
                            value: 'stock_id',
                        },
                        {
                            name: 'Product SKU',
                            value: 'product_sku',
                        },
                    ],
                    default: 'stock_id',
                    description: 'Choose to identify stock by Stock ID or Product SKU',
                },
                // Product: Update Stock - Stock ID
                {
                    displayName: 'Stock ID',
                    name: 'stockId',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['updateStock'],
                            stockIdentifierType: ['stock_id'],
                        },
                    },
                    description: 'ID of the stock to update',
                },
                // Product: Update Stock - Product SKU
                {
                    displayName: 'Product SKU',
                    name: 'productSku',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['updateStock'],
                            stockIdentifierType: ['product_sku'],
                        },
                    },
                    description: 'SKU of the product to update stock for',
                },
                // Product: Update Stock - Action
                {
                    displayName: 'Action',
                    name: 'stockAction',
                    type: 'options',
                    required: true,
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['updateStock'],
                        },
                    },
                    options: [
                        {
                            name: 'Credit',
                            value: 'CREDIT',
                        },
                        {
                            name: 'Debit',
                            value: 'DEBIT',
                        },
                        {
                            name: 'Set',
                            value: 'SET',
                        },
                    ],
                    default: 'SET',
                    description: 'Action to perform on stock: Credit (add), Debit (remove), or Set (replace)',
                },
                // Product: Update Stock - Stock Quantity
                {
                    displayName: 'Stock Quantity',
                    name: 'stock_quantity',
                    type: 'number',
                    required: true,
                    default: 0,
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['updateStock'],
                        },
                    },
                    description: 'Quantity to credit, debit, or set',
                },
                // Product: Update Stock - Comment
                {
                    displayName: 'Comment',
                    name: 'comment',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['updateStock'],
                        },
                    },
                    description: 'Comment for the stock update',
                },
                // ==================== PRODUCT: GET MASTER OPTIONS ====================
                // Product: Get Master Options - Master Option ID
                {
                    displayName: 'Master Option ID',
                    name: 'masterOptionId',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getMasterOptions'],
                        },
                    },
                    description: 'ID of the master option to retrieve',
                },
                // Product: Get Master Options - Fields Selection
                {
                    displayName: 'Master Options Fields',
                    name: 'masterOptionsFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getMasterOptions'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Master Option ID', value: 'master_option_id' },
                        { name: 'Title', value: 'title' },
                        { name: 'Description', value: 'description' },
                        { name: 'Option Key', value: 'option_key' },
                        { name: 'Pricing Method', value: 'pricing_method' },
                        { name: 'Status', value: 'status' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Options Type', value: 'options_type' },
                        { name: 'Linear Formula', value: 'linear_formula' },
                        { name: 'Formula', value: 'formula' },
                        { name: 'Weight Setting', value: 'weight_setting' },
                        { name: 'Price Range Lookup', value: 'price_range_lookup' },
                        { name: 'Additional Lookup Details', value: 'additional_lookup_details' },
                        { name: 'Hide From Calc', value: 'hide_from_calc' },
                        { name: 'Enable Assoc Qty', value: 'enable_assoc_qty' },
                        { name: 'Allow Price Cal', value: 'allow_price_cal' },
                        { name: 'Hire Designer Option', value: 'hire_designer_option' },
                        { name: 'Required', value: 'required' },
                        { name: 'Display In Calculator', value: 'display_in_calculator' },
                        { name: 'Option Position', value: 'option_position' },
                        { name: 'Desc Position', value: 'desc_position' },
                        { name: 'Display Above Size', value: 'display_above_size' },
                        { name: 'Presentation Group', value: 'presentation_group' },
                        { name: 'Export Group ID', value: 'prod_add_opt_export_group_id' },
                        { name: 'Exclude Setup Cost Reorder', value: 'exclude_setup_cost_reorder' },
                        { name: 'Master Option Tag', value: 'master_option_tag' },
                        { name: 'Attributes', value: 'attributes' },
                    ],
                    default: [
                        'master_option_id',
                        'title',
                        'description',
                        'option_key',
                        'pricing_method',
                        'status',
                        'sort_order',
                        'options_type',
                        'linear_formula',
                        'formula',
                        'weight_setting',
                        'price_range_lookup',
                        'additional_lookup_details',
                        'hide_from_calc',
                        'enable_assoc_qty',
                        'allow_price_cal',
                        'hire_designer_option',
                        'required',
                        'display_in_calculator',
                        'option_position',
                        'desc_position',
                        'display_above_size',
                        'presentation_group',
                        'prod_add_opt_export_group_id',
                        'exclude_setup_cost_reorder',
                        'master_option_tag',
                        'attributes',
                    ],
                    description: 'Select master options fields to return. All fields selected by default.',
                },
                // Product: Get Many Master Options - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManyMasterOptions',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyMasterOptions'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Master Option ID',
                            name: 'master_option_id',
                            type: 'string',
                            default: '',
                            description: 'Filter by specific master option ID',
                        },
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of records to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of records to skip',
                        },
                    ],
                },
                // Product: Get Many Master Options - Fields Selection
                {
                    displayName: 'Master Options Fields',
                    name: 'masterOptionsFieldsMany',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyMasterOptions'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Master Option ID', value: 'master_option_id' },
                        { name: 'Title', value: 'title' },
                        { name: 'Description', value: 'description' },
                        { name: 'Option Key', value: 'option_key' },
                        { name: 'Pricing Method', value: 'pricing_method' },
                        { name: 'Status', value: 'status' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Options Type', value: 'options_type' },
                        { name: 'Linear Formula', value: 'linear_formula' },
                        { name: 'Formula', value: 'formula' },
                        { name: 'Weight Setting', value: 'weight_setting' },
                        { name: 'Price Range Lookup', value: 'price_range_lookup' },
                        { name: 'Additional Lookup Details', value: 'additional_lookup_details' },
                        { name: 'Hide From Calc', value: 'hide_from_calc' },
                        { name: 'Enable Assoc Qty', value: 'enable_assoc_qty' },
                        { name: 'Allow Price Cal', value: 'allow_price_cal' },
                        { name: 'Hire Designer Option', value: 'hire_designer_option' },
                        { name: 'Required', value: 'required' },
                        { name: 'Display In Calculator', value: 'display_in_calculator' },
                        { name: 'Option Position', value: 'option_position' },
                        { name: 'Desc Position', value: 'desc_position' },
                        { name: 'Display Above Size', value: 'display_above_size' },
                        { name: 'Presentation Group', value: 'presentation_group' },
                        { name: 'Export Group ID', value: 'prod_add_opt_export_group_id' },
                        { name: 'Exclude Setup Cost Reorder', value: 'exclude_setup_cost_reorder' },
                        { name: 'Master Option Tag', value: 'master_option_tag' },
                        { name: 'Attributes', value: 'attributes' },
                    ],
                    default: [
                        'master_option_id',
                        'title',
                        'description',
                        'option_key',
                        'pricing_method',
                        'status',
                        'sort_order',
                        'options_type',
                        'linear_formula',
                        'formula',
                        'weight_setting',
                        'price_range_lookup',
                        'additional_lookup_details',
                        'hide_from_calc',
                        'enable_assoc_qty',
                        'allow_price_cal',
                        'hire_designer_option',
                        'required',
                        'display_in_calculator',
                        'option_position',
                        'desc_position',
                        'display_above_size',
                        'presentation_group',
                        'prod_add_opt_export_group_id',
                        'exclude_setup_cost_reorder',
                        'master_option_tag',
                        'attributes',
                    ],
                    description: 'Select master options fields to return. All fields selected by default.',
                },
                // ==================== PRODUCT: GET OPTIONS RULES ====================
                // Product: Get Options Rules - Rule ID
                {
                    displayName: 'Rule ID',
                    name: 'ruleId',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getOptionsRules'],
                        },
                    },
                    description: 'ID of the rule to retrieve',
                },
                // Product: Get Options Rules - Fields Selection
                {
                    displayName: 'Options Rules Fields',
                    name: 'optionsRulesFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getOptionsRules'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Rule ID', value: 'rule_id' },
                        { name: 'Rule Name', value: 'rule_name' },
                        { name: 'Rule Type', value: 'rule_type' },
                        { name: 'Source Option Attribute IDs', value: 'source_option_attribute_ids' },
                        { name: 'Hide Option IDs', value: 'hide_option_ids' },
                        { name: 'Hide Option Attribute IDs', value: 'hide_option_attribute_ids' },
                        { name: 'Status', value: 'status' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Comparison Value', value: 'comparison_value' },
                        { name: 'Disabled For Admin', value: 'disabled_for_admin' },
                    ],
                    default: [
                        'rule_id',
                        'rule_name',
                        'rule_type',
                        'source_option_attribute_ids',
                        'hide_option_ids',
                        'hide_option_attribute_ids',
                        'status',
                        'sort_order',
                        'comparison_value',
                        'disabled_for_admin',
                    ],
                    description: 'Select options rules fields to return. All fields selected by default.',
                },
                // Product: Get Many Options Rules - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManyOptionsRules',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyOptionsRules'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Rule ID',
                            name: 'rule_id',
                            type: 'string',
                            default: '',
                            description: 'Filter by specific rule ID',
                        },
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of records to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of records to skip',
                        },
                    ],
                },
                // Product: Get Many Options Rules - Fields Selection
                {
                    displayName: 'Options Rules Fields',
                    name: 'optionsRulesFieldsMany',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyOptionsRules'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Rule ID', value: 'rule_id' },
                        { name: 'Rule Name', value: 'rule_name' },
                        { name: 'Rule Type', value: 'rule_type' },
                        { name: 'Source Option Attribute IDs', value: 'source_option_attribute_ids' },
                        { name: 'Hide Option IDs', value: 'hide_option_ids' },
                        { name: 'Hide Option Attribute IDs', value: 'hide_option_attribute_ids' },
                        { name: 'Status', value: 'status' },
                        { name: 'Sort Order', value: 'sort_order' },
                        { name: 'Comparison Value', value: 'comparison_value' },
                        { name: 'Disabled For Admin', value: 'disabled_for_admin' },
                    ],
                    default: [
                        'rule_id',
                        'rule_name',
                        'rule_type',
                        'source_option_attribute_ids',
                        'hide_option_ids',
                        'hide_option_attribute_ids',
                        'status',
                        'sort_order',
                        'comparison_value',
                        'disabled_for_admin',
                    ],
                    description: 'Select options rules fields to return. All fields selected by default.',
                },
                // ==================== PRODUCT: GET PRICES ====================
                // Product: Get Prices - Product UUID
                {
                    displayName: 'Product UUID',
                    name: 'productIdPrices',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getPrices'],
                        },
                    },
                    description: 'UUID of the product to retrieve prices for',
                },
                // Product: Get Prices - Fields Selection
                {
                    displayName: 'Prices Fields',
                    name: 'pricesFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getPrices'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Size ID', value: 'size_id' },
                        { name: 'Price', value: 'price' },
                        { name: 'Vendor Price', value: 'vendor_price' },
                        { name: 'Qty From', value: 'qty_from' },
                        { name: 'Qty To', value: 'qty_to' },
                        { name: 'Products ID', value: 'products_id' },
                        { name: 'User Type ID', value: 'user_type_id' },
                        { name: 'Corporate ID', value: 'corporate_id' },
                    ],
                    default: [
                        'size_id',
                        'price',
                        'vendor_price',
                        'qty_from',
                        'qty_to',
                        'products_id',
                        'user_type_id',
                        'corporate_id',
                    ],
                    description: 'Select prices fields to return. All fields selected by default.',
                },
                // Product: Get Many Prices - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManyPrices',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyPrices'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Product UUID',
                            name: 'product_uuid',
                            type: 'string',
                            default: '',
                            description: 'Filter by specific product UUID',
                        },
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of records to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of records to skip',
                        },
                    ],
                },
                // Product: Get Many Prices - Fields Selection
                {
                    displayName: 'Prices Fields',
                    name: 'pricesFieldsMany',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyPrices'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Size ID', value: 'size_id' },
                        { name: 'Price', value: 'price' },
                        { name: 'Vendor Price', value: 'vendor_price' },
                        { name: 'Qty From', value: 'qty_from' },
                        { name: 'Qty To', value: 'qty_to' },
                        { name: 'Products ID', value: 'products_id' },
                        { name: 'User Type ID', value: 'user_type_id' },
                        { name: 'Corporate ID', value: 'corporate_id' },
                    ],
                    default: [
                        'size_id',
                        'price',
                        'vendor_price',
                        'qty_from',
                        'qty_to',
                        'products_id',
                        'user_type_id',
                        'corporate_id',
                    ],
                    description: 'Select prices fields to return. All fields selected by default.',
                },
                // ==================== PRODUCT: GET OPTION PRICES ====================
                // Product: Get Option Prices - Attribute ID
                {
                    displayName: 'Attribute ID',
                    name: 'productIdOptionPrices',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getOptionPrices'],
                        },
                    },
                    description: 'Attribute ID to retrieve option prices for',
                },
                // Product: Get Option Prices - Fields Selection
                {
                    displayName: 'Option Prices Fields',
                    name: 'optionPricesFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getOptionPrices'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Attribute ID', value: 'attr_id' },
                        { name: 'Range ID', value: 'range_id' },
                        { name: 'Price', value: 'price' },
                        { name: 'Vendor Price', value: 'vendor_price' },
                        { name: 'From Range', value: 'from_range' },
                        { name: 'To Range', value: 'to_range' },
                        { name: 'Site Admin Markup', value: 'site_admin_markup' },
                    ],
                    default: [
                        'attr_id',
                        'range_id',
                        'price',
                        'vendor_price',
                        'from_range',
                        'to_range',
                        'site_admin_markup',
                    ],
                    description: 'Select option prices fields to return. All fields selected by default.',
                },
                // Product: Get Many Option Prices - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManyOptionPrices',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyOptionPrices'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Attribute ID',
                            name: 'attr_id',
                            type: 'string',
                            default: '',
                            description: 'Filter by specific attribute ID',
                        },
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of records to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of records to skip',
                        },
                    ],
                },
                // Product: Get Many Option Prices - Fields Selection
                {
                    displayName: 'Option Prices Fields',
                    name: 'optionPricesFieldsMany',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyOptionPrices'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Attribute ID', value: 'attr_id' },
                        { name: 'Range ID', value: 'range_id' },
                        { name: 'Price', value: 'price' },
                        { name: 'Vendor Price', value: 'vendor_price' },
                        { name: 'From Range', value: 'from_range' },
                        { name: 'To Range', value: 'to_range' },
                        { name: 'Site Admin Markup', value: 'site_admin_markup' },
                    ],
                    default: [
                        'attr_id',
                        'range_id',
                        'price',
                        'vendor_price',
                        'from_range',
                        'to_range',
                        'site_admin_markup',
                    ],
                    description: 'Select option prices fields to return. All fields selected by default.',
                },
                // ==================== PRODUCT: GET FAQS ====================
                // Product: Get FAQs - FAQ ID Field
                {
                    displayName: 'FAQ ID',
                    name: 'faqId',
                    type: 'number',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getFAQs'],
                        },
                    },
                    description: 'ID of the FAQ to retrieve',
                },
                // Product: Get FAQs - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersFAQs',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getFAQs'],
                        },
                    },
                    options: [
                        {
                            displayName: 'FAQ ID',
                            name: 'faq_id',
                            type: 'number',
                            default: '',
                            description: 'Filter FAQs by specific FAQ ID',
                        },
                        {
                            displayName: 'FAQ Category ID',
                            name: 'faqcat_id',
                            type: 'number',
                            default: '',
                            description: 'Filter FAQs by category ID',
                        },
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of FAQs to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of FAQs to skip',
                        },
                    ],
                },
                // Product: Get FAQs - Fields Selection
                {
                    displayName: 'FAQ Fields',
                    name: 'faqFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getFAQs'],
                        },
                    },
                    options: [
                        {
                            name: 'faq_id',
                            value: 'faq_id',
                        },
                        {
                            name: 'faqcat_id',
                            value: 'faqcat_id',
                        },
                        {
                            name: 'status',
                            value: 'status',
                        },
                        {
                            name: 'sort_order',
                            value: 'sort_order',
                        },
                        {
                            name: 'faq_type',
                            value: 'faq_type',
                        },
                        {
                            name: 'faq_question',
                            value: 'faq_question',
                        },
                        {
                            name: 'faq_answer',
                            value: 'faq_answer',
                        },
                        {
                            name: 'faq_category_name',
                            value: 'faq_category_name',
                        },
                        {
                            name: 'product_ids',
                            value: 'product_ids',
                        },
                        {
                            name: 'category_ids',
                            value: 'category_ids',
                        },
                    ],
                    default: [
                        'faq_id',
                        'faqcat_id',
                        'status',
                        'sort_order',
                        'faq_type',
                        'faq_question',
                        'faq_answer',
                        'faq_category_name',
                        'product_ids',
                        'category_ids',
                    ],
                    description: 'Select FAQ fields to return. All fields selected by default.',
                },
                // Product: Get Many FAQs - Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPagesFAQs',
                    type: 'boolean',
                    default: false,
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyFAQs'],
                        },
                    },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)',
                },
                // Product: Get Many FAQs - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManyFAQs',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyFAQs'],
                        },
                    },
                    options: [
                        {
                            displayName: 'FAQ ID',
                            name: 'faq_id',
                            type: 'number',
                            default: '',
                            description: 'Filter FAQs by specific FAQ ID',
                        },
                        {
                            displayName: 'FAQ Category ID',
                            name: 'faqcat_id',
                            type: 'number',
                            default: '',
                            description: 'Filter FAQs by category ID',
                        },
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of FAQs to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of FAQs to skip',
                        },
                    ],
                },
                // Product: Get Many FAQs - Fields Selection
                {
                    displayName: 'FAQ Fields',
                    name: 'faqFieldsMany',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getManyFAQs'],
                        },
                    },
                    options: [
                        {
                            name: 'faq_id',
                            value: 'faq_id',
                        },
                        {
                            name: 'faqcat_id',
                            value: 'faqcat_id',
                        },
                        {
                            name: 'status',
                            value: 'status',
                        },
                        {
                            name: 'sort_order',
                            value: 'sort_order',
                        },
                        {
                            name: 'faq_type',
                            value: 'faq_type',
                        },
                        {
                            name: 'faq_question',
                            value: 'faq_question',
                        },
                        {
                            name: 'faq_answer',
                            value: 'faq_answer',
                        },
                        {
                            name: 'faq_category_name',
                            value: 'faq_category_name',
                        },
                        {
                            name: 'product_ids',
                            value: 'product_ids',
                        },
                        {
                            name: 'category_ids',
                            value: 'category_ids',
                        },
                    ],
                    default: [
                        'faq_id',
                        'faqcat_id',
                        'status',
                        'sort_order',
                        'faq_type',
                        'faq_question',
                        'faq_answer',
                        'faq_category_name',
                        'product_ids',
                        'category_ids',
                    ],
                    description: 'Select FAQ fields to return. All fields selected by default.',
                },
                // Status Operations
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    displayOptions: {
                        show: {
                            resource: ['status'],
                        },
                    },
                    options: [
                        {
                            name: 'Get Status',
                            value: 'getStatus',
                            description: 'Get a single status by ID',
                            action: 'Get a status',
                        },
                        {
                            name: 'Get Many Status',
                            value: 'getManyStatus',
                            description: 'Get many statuses',
                            action: 'Get many statuses',
                        },
                    ],
                    default: 'getStatus',
                },
                // Status: Get Status - Process Status ID
                {
                    displayName: 'Process Status ID',
                    name: 'processStatusId',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['status'],
                            operation: ['getStatus'],
                        },
                    },
                    description: 'ID of the process status to retrieve',
                },
                // Status: Get Status - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersStatus',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['status'],
                            operation: ['getStatus'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of statuses to return',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of statuses to skip',
                        },
                    ],
                },
                // Status: Get Status - Status Fields Selection
                {
                    displayName: 'Status Fields',
                    name: 'statusFields',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['status'],
                            operation: ['getStatus'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Process Status ID', value: 'process_status_id' },
                        { name: 'Process Status Title', value: 'process_status_title' },
                        { name: 'Status Type', value: 'status_type' },
                        { name: 'Process Status Set As', value: 'process_status_set_as' },
                        { name: 'Process Status Internal', value: 'process_status_internal' },
                    ],
                    default: [
                        'process_status_id',
                        'process_status_title',
                        'status_type',
                        'process_status_set_as',
                        'process_status_internal',
                    ],
                    description: 'Select status fields to return',
                },
                // Status: Get Many Status - Fetch All Pages
                {
                    displayName: 'Fetch All Pages',
                    name: 'fetchAllPages',
                    type: 'boolean',
                    default: false,
                    displayOptions: {
                        show: {
                            resource: ['status'],
                            operation: ['getManyStatus'],
                        },
                    },
                    description: 'Automatically fetch all pages until no more records are available (ignores limit/offset)',
                },
                // Status: Get Many Status - Query Parameters
                {
                    displayName: 'Query Parameters',
                    name: 'queryParametersManyStatus',
                    type: 'collection',
                    placeholder: 'Add Parameter',
                    default: {},
                    displayOptions: {
                        show: {
                            resource: ['status'],
                            operation: ['getManyStatus'],
                        },
                    },
                    options: [
                        {
                            displayName: 'Limit',
                            name: 'limit',
                            type: 'number',
                            default: 50,
                            description: 'Maximum number of statuses to return per page (max 250). Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Offset',
                            name: 'offset',
                            type: 'number',
                            default: 0,
                            description: 'Number of statuses to skip. Ignored when "Fetch All Pages" is enabled.',
                        },
                        {
                            displayName: 'Page Size',
                            name: 'pageSize',
                            type: 'number',
                            typeOptions: {
                                minValue: 1,
                                maxValue: 250,
                            },
                            default: 250,
                            description: 'Records per page when "Fetch All Pages" is enabled (max 250 - API hard limit). Ignored for single page requests.',
                        },
                        {
                            displayName: 'Delay Between Pages (ms)',
                            name: 'pageDelay',
                            type: 'number',
                            typeOptions: {
                                minValue: 25,
                            },
                            default: 50,
                            description: 'Delay between API calls when "Fetch All Pages" is enabled (default 50ms for better performance, min 25ms). Ignored for single page requests.',
                        },
                    ],
                },
                // Status: Get Many Status - Status Type Filter
                {
                    displayName: 'Status Type Filter',
                    name: 'statusTypeFilter',
                    type: 'options',
                    displayOptions: {
                        show: {
                            resource: ['status'],
                            operation: ['getManyStatus'],
                        },
                    },
                    options: [
                        {
                            name: 'Both',
                            value: 'both',
                            description: 'Show both Order and Product statuses',
                        },
                        {
                            name: 'Order Only',
                            value: 'order',
                            description: 'Show only Order statuses',
                        },
                        {
                            name: 'Product Only',
                            value: 'product',
                            description: 'Show only Product statuses',
                        },
                    ],
                    default: 'both',
                    description: 'Filter statuses by type',
                },
                // Status: Get Many Status - Status Fields Selection
                {
                    displayName: 'Status Fields',
                    name: 'statusFieldsMany',
                    type: 'multiOptions',
                    displayOptions: {
                        show: {
                            resource: ['status'],
                            operation: ['getManyStatus'],
                        },
                    },
                    options: [
                        { name: '🔘 Select All Fields', value: 'SELECT_ALL' },
                        { name: '🔘 Deselect All Fields', value: 'DESELECT_ALL' },
                        { name: '─────────────────────────────', value: 'SEPARATOR' },
                        { name: 'Process Status ID', value: 'process_status_id' },
                        { name: 'Process Status Title', value: 'process_status_title' },
                        { name: 'Status Type', value: 'status_type' },
                        { name: 'Process Status Set As', value: 'process_status_set_as' },
                        { name: 'Process Status Internal', value: 'process_status_internal' },
                    ],
                    default: [
                        'process_status_id',
                        'process_status_title',
                        'status_type',
                        'process_status_set_as',
                        'process_status_internal',
                    ],
                    description: 'Select status fields to return',
                },
                // Product: Get Product Details - Product ID
                {
                    displayName: 'Product ID',
                    name: 'productIdDetails',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getProductDetails'],
                        },
                    },
                    description: 'ID of the product to retrieve detailed information for',
                },
                // Product: Get Product Master Options - Product ID
                {
                    displayName: 'Product ID',
                    name: 'productIdMasterOptions',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getProductMasterOptions'],
                        },
                    },
                    description: 'ID of the product to retrieve master options for',
                },
                // Product: Get Product Options Rules - Product ID
                {
                    displayName: 'Product ID',
                    name: 'productIdOptionsRules',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getProductOptionsRules'],
                        },
                    },
                    description: 'ID of the product to retrieve options rules for',
                },
                // Product: Get Product Prices - Product ID
                {
                    displayName: 'Product ID',
                    name: 'productIdPrices',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getProductPrices'],
                        },
                    },
                    description: 'ID of the product to retrieve pricing information for',
                },
                // Product: Get Product Option Prices - Product ID
                {
                    displayName: 'Product ID',
                    name: 'productIdOptionPrices',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getProductOptionPrices'],
                        },
                    },
                    description: 'ID of the product to retrieve option pricing information for',
                },
                // Product: Get Category Details - Category ID
                {
                    displayName: 'Category ID',
                    name: 'categoryIdDetails',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: {
                        show: {
                            resource: ['product'],
                            operation: ['getCategoryDetails'],
                        },
                    },
                    description: 'ID of the category to retrieve detailed information for',
                },
            ],
        };
    }
    async execute() {
        var _a, _b;
        const items = this.getInputData();
        const returnData = [];
        const credentials = await this.getCredentials('onPrintShopApi');
        const baseUrl = stripTrailingSlashes(credentials.baseUrl || 'https://api.onprintshop.com');
        const tokenUrl = stripTrailingSlashes(credentials.tokenUrl || 'https://api.onprintshop.com/oauth/token');
        const clientId = credentials.clientId;
        const clientSecret = credentials.clientSecret;
        const getErrorMessage = (error) => {
            if (error instanceof Error)
                return error.message;
            return String(error);
        };
        const getJsonParameter = (parameterName, itemIndex) => {
            const value = this.getNodeParameter(parameterName, itemIndex);
            if (typeof value === 'string') {
                const trimmed = value.trim();
                if (!trimmed)
                    return {};
                try {
                    return JSON.parse(trimmed);
                }
                catch (error) {
                    throw new n8n_workflow_1.NodeOperationError(this.getNode(), `Invalid JSON in "${parameterName}": ${getErrorMessage(error)}`);
                }
            }
            if (value && typeof value === 'object')
                return value;
            if (value === null || value === undefined)
                return {};
            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `"${parameterName}" must be valid JSON`);
        };
        // Get OAuth2 access token
        let accessToken;
        try {
            const tokenResponse = 
            // Primary: JSON body (some OPS deployments accept this)
            await this.helpers.request({
                method: 'POST',
                url: tokenUrl,
                headers: { 'Content-Type': 'application/json' },
                body: {
                    grant_type: 'client_credentials',
                    client_id: clientId,
                    client_secret: clientSecret,
                },
                json: true,
            }).catch(async (firstError) => {
                // Fallback 1: x-www-form-urlencoded (common OAuth2 client_credentials behavior)
                try {
                    return await this.helpers.request({
                        method: 'POST',
                        url: tokenUrl,
                        form: {
                            grant_type: 'client_credentials',
                            client_id: clientId,
                            client_secret: clientSecret,
                        },
                        json: true,
                    });
                }
                catch (secondError) {
                    // Fallback 2: Basic auth + form (RFC 6749 / many servers)
                    const basicAuth = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');
                    return await this.helpers.request({
                        method: 'POST',
                        url: tokenUrl,
                        headers: { Authorization: `Basic ${basicAuth}` },
                        form: { grant_type: 'client_credentials' },
                        json: true,
                    }).catch(() => {
                        throw firstError;
                    });
                }
            });
            accessToken = tokenResponse === null || tokenResponse === void 0 ? void 0 : tokenResponse.access_token;
            if (!accessToken) {
                throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Failed to get access token: response did not include "access_token"');
            }
        }
        catch (error) {
            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `Failed to get access token: ${getErrorMessage(error)}`);
        }
        for (let i = 0; i < items.length; i++) {
            try {
                const resource = this.getNodeParameter('resource', i);
                const operation = this.getNodeParameter('operation', i);
                if (resource === 'customerAddress' && operation === 'getAll') {
                    const userId = this.getNodeParameter('userId', i);
                    const addressFieldsSelected = this.getNodeParameter('addressFieldsCustomer', i);
                    const addressFields = addressFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const query = `
					query customerAddressDetails ($user_id: Int!) {
						customerAddressDetails (user_id: $user_id) {
							customerAddressDetails {
								${addressFields}
							}
						}
					}
				`;
                    const variables = {
                        user_id: parseInt(String(userId), 10)
                    };
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
                        body: { query: query.trim(), variables },
                        json: true,
                    });
                    if (responseData && responseData.data && responseData.data.customerAddressDetails) {
                        const addresses = responseData.data.customerAddressDetails.customerAddressDetails || [];
                        if (Array.isArray(addresses)) {
                            returnData.push(...addresses);
                        }
                        else if (addresses) {
                            returnData.push(addresses);
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        returnData.push({ error: 'Unexpected response format from API' });
                    }
                }
                if (resource === 'orderDetails' && operation === 'getAll') {
                    const queryParameters = this.getNodeParameter('queryParameters', i);
                    const productFieldsSelected = this.getNodeParameter('productFieldsOrderDetails', i);
                    const fetchAllPages = this.getNodeParameter('fetchAllPages', i, false) || false;
                    const productFields = productFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const query = `
						query orders ($orders_id: Int, $orders_products_id: Int, $order_product_status: Int, $store_id: String, $from_date: String, $to_date: String, $order_status: String, $customer_id: Int, $order_type: OrdersOrderTypeEnum, $limit: Int, $offset: Int) {
							orders (orders_id: $orders_id, orders_products_id: $orders_products_id, order_product_status: $order_product_status, store_id: $store_id, from_date: $from_date, to_date: $to_date, order_status: $order_status, customer_id: $customer_id, order_type: $order_type, limit: $limit, offset: $offset) {
								orders {
									product { ${productFields} }
								}
								totalOrders
							}
						}
					`;
                    let allDetails = [];
                    let totalOrders = 0;
                    let offset = 0;
                    let hasMorePages = true;
                    const pageSize = Math.min(queryParameters.pageSize || 250, 250);
                    let adaptiveDelay = Math.max(queryParameters.pageDelay || 50, 25);
                    if (fetchAllPages) {
                        let pageCount = 0;
                        const maxPages = 100;
                        while (hasMorePages && pageCount < maxPages) {
                            const requestStartTime = Date.now();
                            const variables = { limit: pageSize, offset };
                            const qp = queryParameters || {};
                            if (qp.orders_id !== undefined && qp.orders_id !== '')
                                variables.orders_id = Number(qp.orders_id);
                            if (qp.orders_products_id !== undefined && qp.orders_products_id !== '')
                                variables.orders_products_id = Number(qp.orders_products_id);
                            if (qp.order_product_status !== undefined && qp.order_product_status !== '')
                                variables.order_product_status = Number(qp.order_product_status);
                            if (qp.store_id)
                                variables.store_id = String(qp.store_id);
                            if (qp.from_date)
                                variables.from_date = new Date(String(qp.from_date)).toISOString().split('T')[0];
                            if (qp.to_date)
                                variables.to_date = new Date(String(qp.to_date)).toISOString().split('T')[0];
                            if (qp.order_status)
                                variables.order_status = String(qp.order_status);
                            if (qp.customer_id !== undefined && qp.customer_id !== '')
                                variables.customer_id = Number(qp.customer_id);
                            if (qp.order_type)
                                variables.order_type = qp.order_type;
                            const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: query.trim(), variables }, json: true });
                            if (responseData && responseData.data && responseData.data.orders) {
                                const orders = responseData.data.orders.orders || [];
                                totalOrders = responseData.data.orders.totalOrders;
                                for (const o of orders) {
                                    if (o && o.product)
                                        allDetails.push(o.product);
                                }
                                offset += pageSize;
                                pageCount++;
                                hasMorePages = orders.length === pageSize;
                                const responseTime = Date.now() - requestStartTime;
                                if (responseTime < 100)
                                    adaptiveDelay = Math.max(25, adaptiveDelay * 0.8);
                                else if (responseTime > 500)
                                    adaptiveDelay = Math.min(1000, adaptiveDelay * 1.25);
                                if (hasMorePages)
                                    await new Promise(r => setTimeout(r, Math.round(adaptiveDelay)));
                            }
                            else if (responseData && responseData.errors) {
                                throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                            }
                            else {
                                hasMorePages = false;
                            }
                        }
                        returnData.push(...allDetails);
                    }
                    else {
                        const variables = {};
                        const qp = queryParameters || {};
                        if (qp.orders_id !== undefined && qp.orders_id !== '')
                            variables.orders_id = Number(qp.orders_id);
                        if (qp.orders_products_id !== undefined && qp.orders_products_id !== '')
                            variables.orders_products_id = Number(qp.orders_products_id);
                        if (qp.order_product_status !== undefined && qp.order_product_status !== '')
                            variables.order_product_status = Number(qp.order_product_status);
                        if (qp.store_id)
                            variables.store_id = String(qp.store_id);
                        if (qp.from_date)
                            variables.from_date = new Date(String(qp.from_date)).toISOString().split('T')[0];
                        if (qp.to_date)
                            variables.to_date = new Date(String(qp.to_date)).toISOString().split('T')[0];
                        if (qp.order_status)
                            variables.order_status = String(qp.order_status);
                        if (qp.customer_id !== undefined && qp.customer_id !== '')
                            variables.customer_id = Number(qp.customer_id);
                        if (qp.order_type)
                            variables.order_type = qp.order_type;
                        if (qp.limit)
                            variables.limit = qp.limit;
                        if (qp.offset)
                            variables.offset = qp.offset;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: query.trim(), variables }, json: true });
                        if (responseData && responseData.data && responseData.data.orders) {
                            const orders = responseData.data.orders.orders || [];
                            for (const o of orders) {
                                if (o && o.product)
                                    returnData.push(o.product);
                            }
                        }
                        else if (responseData && responseData.errors) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                        }
                        else {
                            returnData.push({ error: 'Unexpected response format from API' });
                        }
                    }
                }
                if (resource === 'orderShipment' && operation === 'getAll') {
                    const queryParameters = this.getNodeParameter('queryParameters', i);
                    const shipmentFieldsSelected = this.getNodeParameter('shipmentFieldsOrderShipment', i);
                    const fetchAllPages = this.getNodeParameter('fetchAllPages', i, false) || false;
                    const shipmentFields = shipmentFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const query = `
						query orders ($orders_id: Int, $from_date: String, $to_date: String, $order_status: String, $customer_id: Int, $order_type: OrdersOrderTypeEnum, $limit: Int, $offset: Int) {
							orders (orders_id: $orders_id, from_date: $from_date, to_date: $to_date, order_status: $order_status, customer_id: $customer_id, order_type: $order_type, limit: $limit, offset: $offset) {
								orders {
									shipment_detail { ${shipmentFields} }
								}
								totalOrders
							}
						}
					`;
                    let allShipments = [];
                    let totalOrders = 0;
                    let offset = 0;
                    let hasMorePages = true;
                    const pageSize = Math.min(queryParameters.pageSize || 250, 250);
                    let adaptiveDelay = Math.max(queryParameters.pageDelay || 50, 25);
                    if (fetchAllPages) {
                        let pageCount = 0;
                        const maxPages = 100;
                        while (hasMorePages && pageCount < maxPages) {
                            const requestStartTime = Date.now();
                            const variables = { limit: pageSize, offset };
                            const qp = queryParameters || {};
                            if (qp.orders_id !== undefined && qp.orders_id !== '')
                                variables.orders_id = Number(qp.orders_id);
                            if (qp.from_date)
                                variables.from_date = new Date(String(qp.from_date)).toISOString().split('T')[0];
                            if (qp.to_date)
                                variables.to_date = new Date(String(qp.to_date)).toISOString().split('T')[0];
                            if (qp.order_status)
                                variables.order_status = String(qp.order_status);
                            if (qp.customer_id !== undefined && qp.customer_id !== '')
                                variables.customer_id = Number(qp.customer_id);
                            if (qp.order_type)
                                variables.order_type = qp.order_type;
                            const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: query.trim(), variables }, json: true });
                            if (responseData && responseData.data && responseData.data.orders) {
                                const orders = responseData.data.orders.orders || [];
                                totalOrders = responseData.data.orders.totalOrders;
                                for (const o of orders) {
                                    if (o && o.shipment_detail)
                                        allShipments.push(o.shipment_detail);
                                }
                                offset += pageSize;
                                pageCount++;
                                hasMorePages = orders.length === pageSize;
                                const responseTime = Date.now() - requestStartTime;
                                if (responseTime < 100)
                                    adaptiveDelay = Math.max(25, adaptiveDelay * 0.8);
                                else if (responseTime > 500)
                                    adaptiveDelay = Math.min(1000, adaptiveDelay * 1.25);
                                if (hasMorePages)
                                    await new Promise(r => setTimeout(r, Math.round(adaptiveDelay)));
                            }
                            else if (responseData && responseData.errors) {
                                throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                            }
                            else {
                                hasMorePages = false;
                            }
                        }
                        returnData.push(...allShipments);
                    }
                    else {
                        const variables = {};
                        const qp = queryParameters || {};
                        if (qp.orders_id !== undefined && qp.orders_id !== '')
                            variables.orders_id = Number(qp.orders_id);
                        if (qp.from_date)
                            variables.from_date = new Date(String(qp.from_date)).toISOString().split('T')[0];
                        if (qp.to_date)
                            variables.to_date = new Date(String(qp.to_date)).toISOString().split('T')[0];
                        if (qp.order_status)
                            variables.order_status = String(qp.order_status);
                        if (qp.customer_id !== undefined && qp.customer_id !== '')
                            variables.customer_id = Number(qp.customer_id);
                        if (qp.order_type)
                            variables.order_type = qp.order_type;
                        if (qp.limit)
                            variables.limit = qp.limit;
                        if (qp.offset)
                            variables.offset = qp.offset;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: query.trim(), variables }, json: true });
                        if (responseData && responseData.data && responseData.data.orders) {
                            const orders = responseData.data.orders.orders || [];
                            for (const o of orders) {
                                if (o && o.shipment_detail)
                                    returnData.push(o.shipment_detail);
                            }
                        }
                        else if (responseData && responseData.errors) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                        }
                        else {
                            returnData.push({ error: 'Unexpected response format from API' });
                        }
                    }
                }
                if (resource === 'shipToMultipleAddress' && operation === 'getAll') {
                    const order_id = this.getNodeParameter('shipToMultiple_order_id', i);
                    if (!order_id)
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Order ID is required');
                    const stmFieldsSelected = this.getNodeParameter('stmFields', i);
                    const stmFields = stmFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t\t');
                    const query = `
						query shipToMultipleAddress ($order_id: Int) {
							shipToMultipleAddress (order_id: $order_id) {
								shipToMultipleAddress {
									${stmFields}
								}
							}
						}
					`;
                    const variables = { order_id };
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
                        body: { query: query.trim(), variables },
                        json: true,
                    });
                    if (responseData && responseData.data && responseData.data.shipToMultipleAddress) {
                        const rows = responseData.data.shipToMultipleAddress.shipToMultipleAddress || [];
                        if (Array.isArray(rows)) {
                            for (const row of rows)
                                returnData.push({ ...row, _order_id: order_id });
                        }
                        else if (rows) {
                            returnData.push({ ...rows, _order_id: order_id });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'productStocks' && operation === 'getAll') {
                    const productId = this.getNodeParameter('productStocks_product_id', i);
                    if (!productId) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Product ID is required');
                    }
                    const queryParameters = this.getNodeParameter('queryParameters', i);
                    const stockFieldsSelected = this.getNodeParameter('stockFields', i);
                    const fetchAllPages = this.getNodeParameter('fetchAllPages', i, false) || false;
                    const stockFields = stockFieldsSelected
                        .filter(f => !f.startsWith('SELECT_') && !f.startsWith('DESELECT_') && f !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const query = `
						query productStocks ($product_id: Int!, $limit: Int, $offset: Int) {
							productStocks (product_id: $product_id, limit: $limit, offset: $offset) {
								productStocks {
									${stockFields}
								}
								totalProductStocks
							}
						}
					`;
                    let results = [];
                    let offset = 0;
                    const pageSize = Math.min(queryParameters.pageSize || 250, 250);
                    let adaptiveDelay = Math.max(queryParameters.pageDelay || 50, 25);
                    let hasMorePages = true;
                    let pageCount = 0;
                    const maxPages = 100;
                    if (fetchAllPages) {
                        while (hasMorePages && pageCount < maxPages) {
                            const requestStartTime = Date.now();
                            const variables = { product_id: productId, limit: pageSize, offset };
                            const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: query.trim(), variables }, json: true });
                            if (responseData && responseData.data && responseData.data.productStocks) {
                                const stocks = responseData.data.productStocks.productStocks || [];
                                for (const s of stocks)
                                    results.push({ ...s, _totalProductStocks: responseData.data.productStocks.totalProductStocks });
                                offset += pageSize;
                                pageCount++;
                                hasMorePages = stocks.length === pageSize;
                                const responseTime = Date.now() - requestStartTime;
                                if (responseTime < 100)
                                    adaptiveDelay = Math.max(25, adaptiveDelay * 0.8);
                                else if (responseTime > 500)
                                    adaptiveDelay = Math.min(1000, adaptiveDelay * 1.25);
                                if (hasMorePages)
                                    await new Promise(r => setTimeout(r, Math.round(adaptiveDelay)));
                            }
                            else if (responseData && responseData.errors) {
                                throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                            }
                            else {
                                hasMorePages = false;
                            }
                        }
                        returnData.push(...results);
                    }
                    else {
                        const variables = { product_id: productId };
                        if (queryParameters.limit)
                            variables.limit = queryParameters.limit;
                        if (queryParameters.offset)
                            variables.offset = queryParameters.offset;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: query.trim(), variables }, json: true });
                        if (responseData && responseData.data && responseData.data.productStocks) {
                            const stocks = responseData.data.productStocks.productStocks || [];
                            for (const s of stocks) {
                                returnData.push({ ...s, _totalProductStocks: responseData.data.productStocks.totalProductStocks });
                            }
                        }
                        else if (responseData && responseData.errors) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                        }
                        else {
                            returnData.push({ error: 'Unexpected response format from API' });
                        }
                    }
                }
                if (resource === 'status') {
                    const statusFieldsSelected = this.getNodeParameter('statusFields', i);
                    const statusFields = statusFieldsSelected.filter(f => !f.startsWith('SELECT_') && f !== 'DESELECT_ALL' && f !== 'SEPARATOR').join('\n\t\t\t\t\t\t\t');
                    if (operation === 'orderStatus') {
                        const query = `query orderStatus { orderStatus { ${statusFields} } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query }, json: true });
                        if (responseData && responseData.data && responseData.data.orderStatus)
                            returnData.push(...responseData.data.orderStatus);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'orderProductStatus') {
                        const query = `query orderProductStatus { orderProductStatus { ${statusFields} } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query }, json: true });
                        if (responseData && responseData.data && responseData.data.orderProductStatus)
                            returnData.push(...responseData.data.orderProductStatus);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'batch' && operation === 'getAll') {
                    const variables = {};
                    const batchId = this.getNodeParameter('batch_batchId', i);
                    const search = this.getNodeParameter('batch_search', i);
                    const limit = this.getNodeParameter('batch_limit', i);
                    const offset = this.getNodeParameter('batch_offset', i);
                    if (batchId)
                        variables.batch_id = batchId;
                    if (search)
                        variables.search = search;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query getBatch ($batch_id: Int, $search: String, $limit: Int, $offset: Int) { getBatch (batch_id: $batch_id, search: $search, limit: $limit, offset: $offset) { batchDetails { id batch_name nesting_size nest_width nest_height print_count print_instructions finishing_instructions front_print_filename front_cut_filename front_image_link rear_print_filename rear_cut_filename rear_image_link jobs } totalBatchDetails } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.getBatch) {
                        const batches = responseData.data.getBatch.batchDetails || [];
                        for (const b of batches) {
                            returnData.push({ ...b, _totalBatchDetails: responseData.data.getBatch.totalBatchDetails });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'quote' && operation === 'getAll') {
                    const variables = {};
                    const quoteId = this.getNodeParameter('quote_quoteId', i);
                    const userId = this.getNodeParameter('quote_userId', i);
                    const limit = this.getNodeParameter('quote_limit', i);
                    const offset = this.getNodeParameter('quote_offset', i);
                    if (quoteId)
                        variables.quote_id = quoteId;
                    if (userId)
                        variables.user_id = userId;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query get_quote ($quote_id: Int, $user_id: Int, $limit: Int, $offset: Int) { get_quote (quote_id: $quote_id, user_id: $user_id, limit: $limit, offset: $offset) { quote { quote_id user_id quote_title quote_price quote_vendor_price sort_order quote_status quote_date admin_notes quote_shipping_addr quote_billing_addr ship_amt quote_tax_exampt quoteproduct { isCustomProduct quote_products_id quote_id products_id products_title quote_products_quantity quote_products_price quote_products_vendor_price quote_products_info products_prd_day products_weight quote_product_sku quote_product_notes } } totalQuote } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.get_quote) {
                        const quotes = responseData.data.get_quote.quote || [];
                        for (const q of quotes) {
                            returnData.push({ ...q, _totalQuote: responseData.data.get_quote.totalQuote });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'quoteProduct' && operation === 'getAll') {
                    const variables = {};
                    const quoteId = this.getNodeParameter('quoteProduct_quoteId', i);
                    const quoteProductsId = this.getNodeParameter('quoteProduct_quoteProductsId', i);
                    const limit = this.getNodeParameter('quoteProduct_limit', i);
                    const offset = this.getNodeParameter('quoteProduct_offset', i);
                    if (quoteId)
                        variables.quote_id = quoteId;
                    if (quoteProductsId)
                        variables.quote_products_id = quoteProductsId;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query quoteproduct ($quote_id: Int, $quote_products_id: Int, $limit: Int, $offset: Int) { quoteproduct (quote_id: $quote_id, quote_products_id: $quote_products_id, limit: $limit, offset: $offset) { quoteproduct { isCustomProduct quote_products_id quote_id products_id products_title quote_products_quantity quote_products_price quote_products_vendor_price quote_products_info products_prd_day products_weight quote_product_sku quote_product_notes } totalQuoteProduct } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.quoteproduct) {
                        const products = responseData.data.quoteproduct.quoteproduct || [];
                        for (const p of products) {
                            returnData.push({ ...p, _totalQuoteProduct: responseData.data.quoteproduct.totalQuoteProduct });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'store' && operation === 'getAll') {
                    const variables = {};
                    const corporateId = this.getNodeParameter('store_corporateId', i);
                    const email = this.getNodeParameter('store_email', i);
                    const status = this.getNodeParameter('store_status', i);
                    const limit = this.getNodeParameter('store_limit', i);
                    const offset = this.getNodeParameter('store_offset', i);
                    if (corporateId)
                        variables.corporate_id = corporateId;
                    if (email)
                        variables.email = email;
                    if (status)
                        variables.status = status;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query get_store ($corporate_id: Int, $email: String, $status: Int, $limit: Int, $offset: Int) { get_store (corporate_id: $corporate_id, email: $email, status: $status, limit: $limit, offset: $offset) { store { corporate_id email username corporate_name phone_number status tax_exempt tax_exempt_type order_approval price_visible price_text department_module_enable fix_billing_address fix_shipping_address manage_email_notification main_url created_on modified_on url_type parent_corporate_id manage_private_store markup_type flat_markup corporate_markup_id unassigned_products production_days display_in_company_list department { department_id name email_to status cost_center_code production_days created_on modified_on } } totalStore } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.get_store) {
                        const stores = responseData.data.get_store.store || [];
                        for (const s of stores) {
                            returnData.push({ ...s, _totalStore: responseData.data.get_store.totalStore });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'store' && operation === 'get_countries') {
                    const variables = {};
                    const countries_id = this.getNodeParameter('countries_countries_id', i);
                    const status = this.getNodeParameter('countries_status', i);
                    const limit = this.getNodeParameter('countries_limit', i);
                    const offset = this.getNodeParameter('countries_offset', i);
                    if (countries_id)
                        variables.countries_id = countries_id;
                    if (status)
                        variables.status = status;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query get_countries($countries_id: Int, $status: Int, $limit: Int, $offset: Int) { get_countries(countries_id: $countries_id, status: $status, limit: $limit, offset: $offset) { countries { countries_id countries_name countries_iso_code_2 countries_iso_code_3 status } totalCountries } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.get_countries) {
                        const rows = responseData.data.get_countries.countries || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalCountries: responseData.data.get_countries.totalCountries });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'store' && operation === 'get_store_markup') {
                    const variables = {};
                    const corporate_markup_id = this.getNodeParameter('store_markup_corporate_markup_id', i);
                    const limit = this.getNodeParameter('store_markup_limit', i);
                    const offset = this.getNodeParameter('store_markup_offset', i);
                    if (corporate_markup_id)
                        variables.corporate_markup_id = corporate_markup_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query get_store_markup($corporate_markup_id: Int, $limit: Int, $offset: Int) { get_store_markup(corporate_markup_id: $corporate_markup_id, limit: $limit, offset: $offset) { store_markup { corporate_markup_id markup_title markup_details status appliedon } totalStoreMarkup } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.get_store_markup) {
                        const rows = responseData.data.get_store_markup.store_markup || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalStoreMarkup: responseData.data.get_store_markup.totalStoreMarkup });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'store' && operation === 'get_payment_term_master') {
                    const variables = {};
                    const term_id = this.getNodeParameter('payment_term_term_id', i);
                    const limit = this.getNodeParameter('payment_term_limit', i);
                    const offset = this.getNodeParameter('payment_term_offset', i);
                    if (term_id)
                        variables.term_id = term_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query get_payment_term_master($term_id: Int, $limit: Int, $offset: Int) { get_payment_term_master(term_id: $term_id, limit: $limit, offset: $offset) { payment_term_master { term_id term_details default_term check_order status term_title term_description } totalPaymentTermMaster } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.get_payment_term_master) {
                        const rows = responseData.data.get_payment_term_master.payment_term_master || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalPaymentTermMaster: responseData.data.get_payment_term_master.totalPaymentTermMaster });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'store' && operation === 'storeaddress') {
                    const variables = {};
                    const corporate_id = this.getNodeParameter('storeaddress_corporate_id', i);
                    const corporate_address_id = this.getNodeParameter('storeaddress_corporate_address_id', i);
                    const limit = this.getNodeParameter('storeaddress_limit', i);
                    const offset = this.getNodeParameter('storeaddress_offset', i);
                    if (corporate_id)
                        variables.corporate_id = corporate_id;
                    if (corporate_address_id)
                        variables.corporate_address_id = corporate_address_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query storeaddress($corporate_id: Int, $corporate_address_id: Int, $limit: Int, $offset: Int) { storeaddress(corporate_id: $corporate_id, corporate_address_id: $corporate_address_id, limit: $limit, offset: $offset) { storeaddress { office_name corporate_address_id address_flag corporate_id department_id available_to corporate_address suburb city postcode state country country_iso_code phone_number status extrafield receiver_name companyname } totalStoreAddress } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.storeaddress) {
                        const rows = responseData.data.storeaddress.storeaddress || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalStoreAddress: responseData.data.storeaddress.totalStoreAddress });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'store' && operation === 'storeCreditSummary') {
                    const variables = {};
                    const storeid = this.getNodeParameter('storeCreditSummary_storeid', i);
                    const user_id = this.getNodeParameter('storeCreditSummary_user_id', i);
                    const limit = this.getNodeParameter('storeCreditSummary_limit', i);
                    const offset = this.getNodeParameter('storeCreditSummary_offset', i);
                    if (storeid)
                        variables.storeid = storeid;
                    if (user_id)
                        variables.user_id = user_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query storeCreditSummary($storeid: Int, $user_id: Int, $limit: Int, $offset: Int) { storeCreditSummary(storeid: $storeid, user_id: $user_id, limit: $limit, offset: $offset) { storeCreditSummary { user_id storeid customer_name store_name tran_type transaction_msg order_id transaction_date_time maintain_by comments } totalStoreCreditSummary remainingCredit } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.storeCreditSummary) {
                        const result = responseData.data.storeCreditSummary;
                        const rows = result.storeCreditSummary || [];
                        for (const row of rows) {
                            returnData.push({
                                ...row,
                                _totalStoreCreditSummary: result.totalStoreCreditSummary,
                                _remainingCredit: result.remainingCredit,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'store' && operation === 'accountSummary') {
                    const variables = {};
                    const storeid = this.getNodeParameter('accountSummary_storeid', i);
                    const limit = this.getNodeParameter('accountSummary_limit', i);
                    const offset = this.getNodeParameter('accountSummary_offset', i);
                    if (storeid)
                        variables.storeid = storeid;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query accountSummary($storeid: Int, $limit: Int, $offset: Int) { accountSummary(storeid: $storeid, limit: $limit, offset: $offset) { accountSummary { storeid department_id amount type comments paymethod duedate term_title date_added } totalAccountSummary remainingInvoiceAmount remainingPaidLimit } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.accountSummary) {
                        const result = responseData.data.accountSummary;
                        const rows = result.accountSummary || [];
                        for (const row of rows) {
                            returnData.push({
                                ...row,
                                _totalAccountSummary: result.totalAccountSummary,
                                _remainingInvoiceAmount: result.remainingInvoiceAmount,
                                _remainingPaidLimit: result.remainingPaidLimit,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'department' && operation === 'getAll') {
                    const variables = {};
                    const departmentId = this.getNodeParameter('department_departmentId', i);
                    const corporateId = this.getNodeParameter('department_corporateId', i);
                    const limit = this.getNodeParameter('department_limit', i);
                    const offset = this.getNodeParameter('department_offset', i);
                    if (departmentId)
                        variables.department_id = departmentId;
                    if (corporateId)
                        variables.corporate_id = corporateId;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query get_departments ($department_id: Int, $corporate_id: Int, $limit: Int, $offset: Int) { get_departments (department_id: $department_id, corporate_id: $corporate_id, limit: $limit, offset: $offset) { departments { department_id corporate_id name email_to status cost_center_code production_days created_on modified_on } totalDepartments } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.get_departments) {
                        const departments = responseData.data.get_departments.departments || [];
                        for (const d of departments) {
                            returnData.push({ ...d, _totalDepartments: responseData.data.get_departments.totalDepartments });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'mutation') {
                    if (operation === 'updateOrderStatus') {
                        const type = this.getNodeParameter('statusUpdateType', i);
                        const variables = {
                            type,
                            input: getJsonParameter('updateOrderStatusInput', i),
                        };
                        if (type === 'order') {
                            const orders_id = this.getNodeParameter('orders_id', i);
                            if (!orders_id) {
                                throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Orders ID is required when Type is "Order"');
                            }
                            variables.orders_id = orders_id;
                        }
                        else {
                            const orders_products_id = this.getNodeParameter('orders_products_id', i);
                            if (!orders_products_id) {
                                throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Orders Products ID is required when Type is "Product"');
                            }
                            variables.orders_products_id = orders_products_id;
                        }
                        const mutation = `mutation updateOrderStatus ($type: OrderStatusUpdateTypeEnum!, $orders_id: Int, $orders_products_id: Int, $input: UpdateOrderStatusInput!) { updateOrderStatus (type: $type, orders_id: $orders_id, orders_products_id: $orders_products_id, input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.updateOrderStatus)
                            returnData.push(responseData.data.updateOrderStatus);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setOrderProduct') {
                        const order_product_id = this.getNodeParameter('setOrderProduct_order_product_id', i);
                        const width = this.getNodeParameter('setOrderProduct_width', i);
                        const height = this.getNodeParameter('setOrderProduct_height', i);
                        const input = getJsonParameter('setOrderProduct_input', i);
                        const variables = { input };
                        if (order_product_id)
                            variables.order_product_id = order_product_id;
                        if (width)
                            variables.width = width;
                        if (height)
                            variables.height = height;
                        const mutation = `mutation setOrderProduct ($order_product_id: Int, $width: Float, $height: Float, $input: SetOrderProductInput!) { setOrderProduct (order_product_id: $order_product_id, width: $width, height: $height, input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setOrderProduct)
                            returnData.push(responseData.data.setOrderProduct);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setBatch') {
                        const batch_id = this.getNodeParameter('setBatch_batch_id', i);
                        const input = getJsonParameter('setBatch_input', i);
                        const variables = { batch_id, input };
                        const mutation = `mutation setBatch ($batch_id: Int, $input: SetBatchMasterInput!) { setBatch (batch_id: $batch_id, input: $input) { result message batch_id batch_link batch_pdf_link } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setBatch)
                            returnData.push(responseData.data.setBatch);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setProduct') {
                        const input = getJsonParameter('setProduct_input', i);
                        const mutation = `mutation setProduct ($input: ProductInput!) { setProduct (input: $input) { result message products_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setProduct)
                            returnData.push(responseData.data.setProduct);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setProductPrice') {
                        const input = getJsonParameter('setProductPrice_input', i);
                        const mutation = `mutation setProductPrice ($input: ProductPriceInput!) { setProductPrice (input: $input) { result message product_price_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setProductPrice)
                            returnData.push(responseData.data.setProductPrice);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setProductSize') {
                        const input = getJsonParameter('setProductSize_input', i);
                        const mutation = `mutation setProductSize ($input: ProductSizeInput!) { setProductSize (input: $input) { result message product_size_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setProductSize)
                            returnData.push(responseData.data.setProductSize);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setProductCategory') {
                        const input = getJsonParameter('setProductCategory_input', i);
                        const mutation = `mutation setProductCategory ($input: ProductCategoryInput!) { setProductCategory (input: $input) { result message category_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setProductCategory)
                            returnData.push(responseData.data.setProductCategory);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setQuote') {
                        const userid = this.getNodeParameter('setQuote_userid', i);
                        const quote_id = this.getNodeParameter('setQuote_quote_id', i);
                        const quote_title = this.getNodeParameter('setQuote_quote_title', i);
                        const selectedShippingType = this.getNodeParameter('setQuote_selectedShippingType', i);
                        const input = getJsonParameter('setQuote_input', i);
                        const variables = { userid, quote_title, input };
                        if (quote_id)
                            variables.quote_id = quote_id;
                        if (selectedShippingType)
                            variables.selectedShippingType = selectedShippingType;
                        const mutation = `mutation setQuote ($userid: Int!, $quote_id: Int, $selectedShippingType: String, $quote_title: String!, $input: SetQuoteInput!) { setQuote (userid: $userid, quote_title: $quote_title, selectedShippingType: $selectedShippingType, quote_id: $quote_id, input: $input) { result message quote_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setQuote)
                            returnData.push(responseData.data.setQuote);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setProductDesign') {
                        const order_product_id = this.getNodeParameter('setProductDesign_order_product_id', i);
                        const ziflow_link = this.getNodeParameter('setProductDesign_ziflow_link', i);
                        const ziflow_preflight_link = this.getNodeParameter('setProductDesign_ziflow_preflight_link', i);
                        const variables = {};
                        if (order_product_id)
                            variables.order_product_id = order_product_id;
                        if (ziflow_link)
                            variables.ziflow_link = ziflow_link;
                        if (ziflow_preflight_link)
                            variables.ziflow_preflight_link = ziflow_preflight_link;
                        const mutation = `mutation setProductDesign ($order_product_id: Int, $ziflow_link: String, $ziflow_preflight_link: String) { setProductDesign (order_product_id: $order_product_id, ziflow_link: $ziflow_link, ziflow_preflight_link: $ziflow_preflight_link) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setProductDesign)
                            returnData.push(responseData.data.setProductDesign);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'updateOrderProductImages') {
                        const order_product_id = this.getNodeParameter('updateOrderProductImages_order_product_id', i);
                        const input = getJsonParameter('updateOrderProductImages_input', i);
                        const variables = { input };
                        if (order_product_id)
                            variables.order_product_id = order_product_id;
                        const mutation = `mutation setOrderProductImage ($order_product_id: Int, $input: SetOrderProductImageInput!) { setOrderProductImage (order_product_id: $order_product_id, input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setOrderProductImage)
                            returnData.push(responseData.data.setOrderProductImage);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'addProofVersion') {
                        const order_product_id = this.getNodeParameter('addProofVersion_order_product_id', i);
                        const add_version_file_only = this.getNodeParameter('addProofVersion_add_version_file_only', i);
                        const ask_for_approval = this.getNodeParameter('addProofVersion_ask_for_approval', i);
                        const input = getJsonParameter('addProofVersion_input', i);
                        const variables = { update_ziflow_link_only: 0, add_version_file_only, ask_for_approval, input };
                        if (order_product_id)
                            variables.order_product_id = order_product_id;
                        const mutation = `mutation setOrderProductImage ($order_product_id: Int, $update_ziflow_link_only: Int, $add_version_file_only: Int, $ask_for_approval: Int, $input: SetOrderProductImageInput!) { setOrderProductImage (order_product_id: $order_product_id, update_ziflow_link_only: $update_ziflow_link_only, add_version_file_only: $add_version_file_only, ask_for_approval: $ask_for_approval, input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setOrderProductImage)
                            returnData.push(responseData.data.setOrderProductImage);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'updateZiflowLinkImages') {
                        const order_product_id = this.getNodeParameter('updateZiflowLinkImages_order_product_id', i);
                        const input = getJsonParameter('updateZiflowLinkImages_input', i);
                        const variables = { update_ziflow_link_only: 1, input };
                        if (order_product_id)
                            variables.order_product_id = order_product_id;
                        const mutation = `mutation setOrderProductImage ($order_product_id: Int, $update_ziflow_link_only: Int, $input: SetOrderProductImageInput!) { setOrderProductImage (order_product_id: $order_product_id, update_ziflow_link_only: $update_ziflow_link_only, input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setOrderProductImage)
                            returnData.push(responseData.data.setOrderProductImage);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'notifyUser') {
                        const usertype = this.getNodeParameter('notifyUser_usertype', i);
                        const cust_id = this.getNodeParameter('notifyUser_cust_id', i);
                        const input = getJsonParameter('notifyUser_input', i);
                        const variables = { usertype, input };
                        if (cust_id)
                            variables.cust_id = cust_id;
                        const mutation = `mutation notifyUser ($usertype: UserNotifyTypeEnum!, $cust_id: Int, $input: UserNotifyInput!) { notifyUser (cust_id: $cust_id, usertype: $usertype, input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.notifyUser)
                            returnData.push(responseData.data.notifyUser);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setShipment') {
                        const order_id = this.getNodeParameter('setShipment_order_id', i);
                        const shipment_id = this.getNodeParameter('setShipment_shipment_id', i);
                        const tracking_number = this.getNodeParameter('setShipment_tracking_number', i);
                        const shipmentinfo = getJsonParameter('setShipment_shipmentinfo', i);
                        const variables = { order_id, shipment_id, tracking_number, shipmentinfo };
                        const mutation = `mutation setShipment ($order_id: Int,$shipment_id: Int,$tracking_number: String, $shipmentinfo: JSON) { setShipment (order_id: $order_id, shipment_id: $shipment_id, tracking_number: $tracking_number, shipmentinfo: $shipmentinfo) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setShipment)
                            returnData.push(responseData.data.setShipment);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setCustomer') {
                        const customer_id = this.getNodeParameter('setCustomer_customer_id', i);
                        const input = getJsonParameter('setCustomer_input', i);
                        const variables = { customer_id, input };
                        const mutation = `mutation setCustomer ($customer_id: Int, $input: SetCustomerInput!) { setCustomer (customer_id: $customer_id, input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setCustomer)
                            returnData.push(responseData.data.setCustomer);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setCustomerAddressDetail') {
                        const input = getJsonParameter('setCustomerAddressDetail_input', i);
                        const mutation = `mutation setCustomerAddressDetail ($input: CustomerAddressInput!) { setCustomerAddressDetail (input: $input) { result message address_book_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setCustomerAddressDetail)
                            returnData.push(responseData.data.setCustomerAddressDetail);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setProductOptionRules') {
                        const input = getJsonParameter('setProductOptionRules_input', i);
                        const mutation = `mutation setProductOptionRules ($input: ProductOptionRulesInput!) { setProductOptionRules (input: $input) { result message rule_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setProductOptionRules)
                            returnData.push(responseData.data.setProductOptionRules);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setCustomFormula') {
                        const input = getJsonParameter('setCustomFormula_input', i);
                        const mutation = `mutation setCustomFormula ($input: CustomFormulaInput!) { setCustomFormula (input: $input) { result message formula_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setCustomFormula)
                            returnData.push(responseData.data.setCustomFormula);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setOptionGroup') {
                        const input = getJsonParameter('setOptionGroup_input', i);
                        const mutation = `mutation setOptionGroup ($input: OptionGroupInput!) { setOptionGroup (input: $input) { result message prod_add_opt_group_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setOptionGroup)
                            returnData.push(responseData.data.setOptionGroup);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setMasterOptionTag') {
                        const input = getJsonParameter('setMasterOptionTag_input', i);
                        const mutation = `mutation setMasterOptionTag ($input: MasterOptionTagInput!) { setMasterOptionTag (input: $input) { result message master_option_tag_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setMasterOptionTag)
                            returnData.push(responseData.data.setMasterOptionTag);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setMasterOptionAttributes') {
                        const input = getJsonParameter('setMasterOptionAttributes_input', i);
                        const mutation = `mutation setMasterOptionAttributes ($input: MasterOptionAttributesInput!) { setMasterOptionAttributes (input: $input) { result message master_attribute_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setMasterOptionAttributes)
                            returnData.push(responseData.data.setMasterOptionAttributes);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setMasterOptionRange') {
                        const input = getJsonParameter('setMasterOptionRange_input', i);
                        const mutation = `mutation setMasterOptionRange ($input: MasterOptionRangeInput!) { setMasterOptionRange (input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setMasterOptionRange)
                            returnData.push(responseData.data.setMasterOptionRange);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setMasterOptionAttributePrice') {
                        const input = getJsonParameter('setMasterOptionAttributePrice_input', i);
                        const mutation = `mutation setMasterOptionAttributePrice ($input: MasterOptionAttributePriceInput!) { setMasterOptionAttributePrice (input: $input) { result message } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setMasterOptionAttributePrice)
                            returnData.push(responseData.data.setMasterOptionAttributePrice);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setMasterOption') {
                        const input = getJsonParameter('setMasterOption_input', i);
                        const mutation = `mutation setMasterOption ($input: MasterOptionInput!) { setMasterOption (input: $input) { result message master_option_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setMasterOption)
                            returnData.push(responseData.data.setMasterOption);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setAssignOptions') {
                        const input = getJsonParameter('setAssignOptions_input', i);
                        const mutation = `mutation setAssignOptions ($input: AssignOptionsInput!) { setAssignOptions (input: $input) { result message product_option_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setAssignOptions)
                            returnData.push(responseData.data.setAssignOptions);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setProductPages') {
                        const input = getJsonParameter('setProductPages_input', i);
                        const mutation = `mutation setProductPages ($input: ProductPagesInput!) { setProductPages (input: $input) { result message product_page_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setProductPages)
                            returnData.push(responseData.data.setProductPages);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setStoreAddress') {
                        const input = getJsonParameter('setStoreAddress_input', i);
                        const mutation = `mutation setStoreAddress ($input: StoreAddressInput!) { setStoreAddress (input: $input) { result message corporate_address_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setStoreAddress)
                            returnData.push(responseData.data.setStoreAddress);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setDepartment') {
                        const input = getJsonParameter('setDepartment_input', i);
                        const mutation = `mutation setDepartment ($input: DepartmentInput!) { setDepartment (input: $input) { result message department_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setDepartment)
                            returnData.push(responseData.data.setDepartment);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setStore') {
                        const input = getJsonParameter('setStore_input', i);
                        const mutation = `mutation setStore ($input: StoreInput!) { setStore (input: $input) { result message corporate_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setStore)
                            returnData.push(responseData.data.setStore);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setStoreMarkup') {
                        const input = getJsonParameter('setStoreMarkup_input', i);
                        const mutation = `mutation setStoreMarkup ($input: StoreMarkupInput!) { setStoreMarkup (input: $input) { result message corporate_markup_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setStoreMarkup)
                            returnData.push(responseData.data.setStoreMarkup);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setFaqCategory') {
                        const input = getJsonParameter('setFaqCategory_input', i);
                        const mutation = `mutation setFaqCategory($input: FaqCategoryInput!) { setFaqCategory(input: $input) { result message faqcat_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setFaqCategory)
                            returnData.push(responseData.data.setFaqCategory);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setFaq') {
                        const input = getJsonParameter('setFaq_input', i);
                        const mutation = `mutation setFaq($input: FaqInput!) { setFaq(input: $input) { result message faq_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setFaq)
                            returnData.push(responseData.data.setFaq);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setOrder') {
                        const userid = this.getNodeParameter('setOrder_userid', i);
                        const order_id = this.getNodeParameter('setOrder_order_id', i);
                        const order_title = this.getNodeParameter('setOrder_order_title', i);
                        const selectedShippingType = this.getNodeParameter('setOrder_selectedShippingType', i);
                        const input = getJsonParameter('setOrder_input', i);
                        const variables = { userid, order_title, input };
                        if (order_id)
                            variables.order_id = order_id;
                        if (selectedShippingType)
                            variables.selectedShippingType = selectedShippingType;
                        const mutation = `mutation setOrder ($userid: Int!, $order_id: Int, $selectedShippingType: Int, $order_title: String!, $input: SetOrderInput!) { setOrder (userid: $userid, order_title: $order_title, selectedShippingType: $selectedShippingType, order_id: $order_id, input: $input) { result message order_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setOrder)
                            returnData.push(responseData.data.setOrder);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setUserBasket') {
                        const userId = this.getNodeParameter('setUserBasket_userId', i);
                        const action = this.getNodeParameter('setUserBasket_action', i);
                        const basketId = this.getNodeParameter('setUserBasket_basketId', i);
                        const itemIndex = this.getNodeParameter('setUserBasket_itemIndex', i);
                        const input = getJsonParameter('setUserBasket_input', i);
                        const variables = { userId, action, basketId, itemIndex, input };
                        const mutation = `mutation setUserBasket ($userId: Int!, $action: String!, $basketId: Int, $itemIndex: Int!, $input: SetUserBasketInput!) { setUserBasket (userId: $userId, action: $action, basketId: $basketId, itemIndex: $itemIndex, input: $input) { result message basket_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.setUserBasket)
                            returnData.push(responseData.data.setUserBasket);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'modifyOrderProduct') {
                        const orderid = this.getNodeParameter('modifyOrderProduct_orderid', i);
                        const input = getJsonParameter('modifyOrderProduct_input', i);
                        const variables = { orderid, input };
                        const mutation = `mutation modifyOrderProduct ($orderid: Int!, $input: ModifyOrderProductInput!) { modifyOrderProduct (orderid: $orderid, input: $input) { result message results { success message orderProductId } } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.modifyOrderProduct)
                            returnData.push(responseData.data.modifyOrderProduct);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setAdditionalOption') {
                        const input = getJsonParameter('setAdditionalOption_input', i);
                        const mutation = `mutation setAdditionalOption($input: AdditionalOptionInput!) { setAdditionalOption(input: $input) { result message prod_add_opt_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setAdditionalOption)
                            returnData.push(responseData.data.setAdditionalOption);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setAdditionalOptionAttributes') {
                        const input = getJsonParameter('setAdditionalOptionAttributes_input', i);
                        const mutation = `mutation setAdditionalOptionAttributes($input: AdditionalOptionAttributesInput!) { setAdditionalOptionAttributes(input: $input) { result message attribute_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setAdditionalOptionAttributes)
                            returnData.push(responseData.data.setAdditionalOptionAttributes);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setProductsAttributePrice') {
                        const input = getJsonParameter('setProductsAttributePrice_input', i);
                        const mutation = `mutation setProductsAttributePrice($input: ProductsAttributePriceInput!) { setProductsAttributePrice(input: $input) { result message attribute_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setProductsAttributePrice)
                            returnData.push(responseData.data.setProductsAttributePrice);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'setQuantityBasedAttributePrice') {
                        const input = getJsonParameter('setQuantityBasedAttributePrice_input', i);
                        const mutation = `mutation setQuantityBasedAttributePrice($input: QuantityBasedAttributePriceInput!) { setQuantityBasedAttributePrice(input: $input) { result message attribute_id } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
                        if (responseData && responseData.data && responseData.data.setQuantityBasedAttributePrice)
                            returnData.push(responseData.data.setQuantityBasedAttributePrice);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    if (operation === 'updateProductStock') {
                        const stock_id = this.getNodeParameter('updateProductStock_stock_id', i);
                        const product_sku = this.getNodeParameter('updateProductStock_product_sku', i);
                        const action = this.getNodeParameter('updateProductStock_action', i);
                        const input = getJsonParameter('updateProductStock_input', i);
                        const variables = { action, input };
                        if (stock_id)
                            variables.stock_id = stock_id;
                        if (product_sku)
                            variables.product_sku = product_sku;
                        const mutation = `mutation updateProductStock ($stock_id: Int, $product_sku: String, $action: UpdateProductStockActionEnum!, $input: UpdateProductStockInput!) { updateProductStock (stock_id: $stock_id, product_sku: $product_sku, action: $action, input: $input) { result message stock_id stock_quantity } }`;
                        const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
                        if (responseData && responseData.data && responseData.data.updateProductStock)
                            returnData.push(responseData.data.updateProductStock);
                        else if (responseData && responseData.errors)
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                }
                if (resource === 'customer' && operation === 'create') {
                    // Create customer - registration type, first name, last name, and email required
                    const registration_type = this.getNodeParameter('registration_type', i);
                    const first_name = this.getNodeParameter('first_name', i);
                    const last_name = this.getNodeParameter('last_name', i);
                    const email = this.getNodeParameter('email', i);
                    const optionalFields = this.getNodeParameter('optionalFields', i);
                    // Generate password if not provided and doing full registration
                    let password = optionalFields.password || '';
                    // If doing normal registration (not two step) and no password provided, generate one
                    if (registration_type === 0 && !password) {
                        // Generate a random 8-character password
                        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
                        password = '';
                        for (let j = 0; j < 8; j++) {
                            password += chars.charAt(Math.floor(Math.random() * chars.length));
                        }
                    }
                    // Build input object with smart defaults
                    const input = {
                        registration_type,
                        corporateid: optionalFields.corporateid !== undefined ? optionalFields.corporateid : 0,
                        departmentid: optionalFields.departmentid !== undefined ? optionalFields.departmentid : 0,
                        first_name,
                        last_name,
                        email,
                        password: password || '',
                        set_password: registration_type === 0 ? 1 : 0,
                        phone_no: optionalFields.phone_no !== undefined ? optionalFields.phone_no : '',
                        company_name: optionalFields.company_name !== undefined ? optionalFields.company_name : '',
                        user_group: optionalFields.user_group !== undefined ? optionalFields.user_group : 0,
                        secondary_emails: optionalFields.secondary_emails !== undefined ? optionalFields.secondary_emails : '',
                        status: optionalFields.status !== undefined ? optionalFields.status : 1,
                        tax_exemption: optionalFields.tax_exemption !== undefined ? optionalFields.tax_exemption : 0,
                        payon_account: optionalFields.payon_account !== undefined ? optionalFields.payon_account : 0,
                        payon_limit: optionalFields.payon_limit !== undefined ? optionalFields.payon_limit : 0,
                    };
                    // Build the GraphQL mutation
                    const mutation = `
						mutation setCustomer ($customer_id: Int, $input: SetCustomerInput!) {
							setCustomer (customer_id: $customer_id, input: $input) {
								result
								message
							}
						}
					`;
                    // Make the GraphQL request (customer_id = 0 for create)
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: mutation.trim(),
                            variables: {
                                customer_id: 0,
                                input,
                            },
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.setCustomer) {
                        const result = responseData.data.setCustomer;
                        returnData.push({
                            ...result,
                            _operation: 'create',
                            _registration_type: registration_type === 0 ? 'Normal' : 'Two Step',
                            _generated_password: registration_type === 0 && password ? password : null,
                            _input: input,
                        });
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'customer' && operation === 'update') {
                    // Update customer
                    const customer_id = this.getNodeParameter('customer_id', i);
                    const updateFields = this.getNodeParameter('updateFields', i);
                    // Build input object with only provided fields
                    const input = {};
                    // Add fields if provided
                    if (updateFields.registration_type !== undefined)
                        input.registration_type = updateFields.registration_type;
                    if (updateFields.corporateid !== undefined)
                        input.corporateid = updateFields.corporateid;
                    if (updateFields.departmentid !== undefined)
                        input.departmentid = updateFields.departmentid;
                    if (updateFields.first_name !== undefined)
                        input.first_name = updateFields.first_name;
                    if (updateFields.last_name !== undefined)
                        input.last_name = updateFields.last_name;
                    if (updateFields.email !== undefined)
                        input.email = updateFields.email;
                    if (updateFields.password !== undefined)
                        input.password = updateFields.password;
                    if (updateFields.set_password !== undefined)
                        input.set_password = updateFields.set_password;
                    if (updateFields.phone_no !== undefined)
                        input.phone_no = updateFields.phone_no;
                    if (updateFields.company_name !== undefined)
                        input.company_name = updateFields.company_name;
                    if (updateFields.user_group !== undefined)
                        input.user_group = updateFields.user_group;
                    if (updateFields.secondary_emails !== undefined)
                        input.secondary_emails = updateFields.secondary_emails;
                    if (updateFields.status !== undefined)
                        input.status = updateFields.status;
                    if (updateFields.tax_exemption !== undefined)
                        input.tax_exemption = updateFields.tax_exemption;
                    if (updateFields.payon_account !== undefined)
                        input.payon_account = updateFields.payon_account;
                    if (updateFields.payon_limit !== undefined)
                        input.payon_limit = updateFields.payon_limit;
                    // Build the GraphQL mutation
                    const mutation = `
						mutation setCustomer ($customer_id: Int, $input: SetCustomerInput!) {
							setCustomer (customer_id: $customer_id, input: $input) {
								result
								message
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: mutation.trim(),
                            variables: {
                                customer_id,
                                input,
                            },
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.setCustomer) {
                        const result = responseData.data.setCustomer;
                        returnData.push({
                            ...result,
                            _operation: 'update',
                            _customer_id: customer_id,
                            _input: input,
                        });
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'customer' && operation === 'get') {
                    // Get customer by email
                    const email = this.getNodeParameter('email', i);
                    const customerFieldsSelected = this.getNodeParameter('customerFields', i);
                    const addressFieldsSelected = this.getNodeParameter('addressFields', i);
                    // Filter out special options and separators
                    const customerFields = customerFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL_') && !field.startsWith('DESELECT_ALL_') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build address fields string
                    let addressFields = '';
                    const validAddressFields = addressFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL_') && !field.startsWith('DESELECT_ALL_') && field !== 'SEPARATOR');
                    if (validAddressFields.length > 0) {
                        const addressFieldsStr = validAddressFields.join('\n\t\t\t\t\t\t\t\t');
                        addressFields = `
							address_detail {
								${addressFieldsStr}
							}
						`;
                    }
                    // Build the GraphQL query
                    const query = `
						query customers ($email: String) {
							customers (email: $email) {
								customers {
									${customerFields}
									${addressFields}
								}
								totalCustomers
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables: { email },
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.customers) {
                        const customers = responseData.data.customers.customers;
                        const totalCustomers = responseData.data.customers.totalCustomers;
                        // Add each customer to returnData
                        if (Array.isArray(customers) && customers.length > 0) {
                            customers.forEach((customer) => {
                                returnData.push({
                                    ...customer,
                                    _totalCustomers: totalCustomers,
                                });
                            });
                        }
                        else {
                            // No customer found
                            returnData.push({
                                error: 'No customer found with this email',
                                email,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'customer' && operation === 'getAll') {
                    // Get query parameters
                    const queryParameters = this.getNodeParameter('queryParameters', i);
                    const customerFieldsSelected = this.getNodeParameter('customerFieldsGetAll', i);
                    const addressFieldsSelected = this.getNodeParameter('addressFieldsGetAll', i);
                    const fetchAllPages = this.getNodeParameter('fetchAllPages', i) || false;
                    const pageSize = Math.min(queryParameters.pageSize || 250, 250); // Max 250 (API hard limit)
                    const pageDelay = Math.max(queryParameters.pageDelay || 50, 25); // Min 25ms, default 50ms
                    // Filter out special options and separators
                    const customerFields = customerFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL_') && !field.startsWith('DESELECT_ALL_') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build address fields string
                    let addressFields = '';
                    const validAddressFields = addressFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL_') && !field.startsWith('DESELECT_ALL_') && field !== 'SEPARATOR');
                    if (validAddressFields.length > 0) {
                        const addressFieldsStr = validAddressFields.join('\n\t\t\t\t\t\t\t\t');
                        addressFields = `
							address_detail {
								${addressFieldsStr}
							}
						`;
                    }
                    // Build the GraphQL query
                    const query = `
						query customers ($email: String, $from_date: String, $to_date: String, $date_type: CustomerDateTypeEnum, $limit: Int, $offset: Int) {
							customers (email: $email, from_date: $from_date, to_date: $to_date, date_type: $date_type, limit: $limit, offset: $offset) {
								customers {
									${customerFields}
									${addressFields}
								}
								totalCustomers
							}
						}
					`;
                    let allCustomers = [];
                    let totalCustomers = 0;
                    let offset = 0;
                    let hasMorePages = true;
                    if (fetchAllPages) {
                        // Auto-pagination: fetch all pages with rate limiting
                        let pageCount = 0;
                        const maxPages = 100; // Safety limit to prevent infinite loops
                        let adaptiveDelay = pageDelay;
                        while (hasMorePages && pageCount < maxPages) {
                            const requestStartTime = Date.now();
                            const variables = {
                                limit: pageSize,
                                offset: offset,
                            };
                            if (queryParameters.email)
                                variables.email = queryParameters.email;
                            if (queryParameters.from_date)
                                variables.from_date = new Date(queryParameters.from_date).toISOString().split('T')[0];
                            if (queryParameters.to_date)
                                variables.to_date = new Date(queryParameters.to_date).toISOString().split('T')[0];
                            if (queryParameters.date_type)
                                variables.date_type = queryParameters.date_type;
                            try {
                                const responseData = await this.helpers.request({
                                    method: 'POST',
                                    url: `${baseUrl}/api/`,
                                    headers: {
                                        'Authorization': `Bearer ${accessToken}`,
                                        'Content-Type': 'application/json',
                                    },
                                    body: {
                                        query: query.trim(),
                                        variables,
                                    },
                                    json: true,
                                });
                                if (responseData && responseData.data && responseData.data.customers) {
                                    const customers = responseData.data.customers.customers;
                                    totalCustomers = responseData.data.customers.totalCustomers;
                                    if (Array.isArray(customers) && customers.length > 0) {
                                        allCustomers = allCustomers.concat(customers);
                                        offset += pageSize;
                                        pageCount++;
                                        hasMorePages = customers.length === pageSize; // Continue if we got a full page
                                        // Adaptive delay: adjust based on response time
                                        const responseTime = Date.now() - requestStartTime;
                                        if (responseTime < 100) {
                                            // Fast response, can reduce delay
                                            adaptiveDelay = Math.max(25, adaptiveDelay * 0.8);
                                        }
                                        else if (responseTime > 500) {
                                            // Slow response, increase delay
                                            adaptiveDelay = Math.min(200, adaptiveDelay * 1.2);
                                        }
                                        // Add adaptive delay between requests
                                        if (hasMorePages) {
                                            await new Promise(resolve => setTimeout(resolve, Math.round(adaptiveDelay)));
                                        }
                                    }
                                    else {
                                        hasMorePages = false;
                                    }
                                }
                                else if (responseData && responseData.errors) {
                                    throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error on page ${pageCount + 1}: ${JSON.stringify(responseData.errors)}`);
                                }
                                else {
                                    hasMorePages = false;
                                }
                            }
                            catch (error) {
                                // Handle rate limiting or server errors
                                if (error.statusCode === 429 || error.statusCode === 502) {
                                    // Rate limited or server error - wait longer and retry
                                    adaptiveDelay = Math.min(1000, adaptiveDelay * 2); // Increase delay on rate limit
                                    await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay
                                    continue; // Retry the same page
                                }
                                else {
                                    throw error; // Re-throw other errors
                                }
                            }
                        }
                        if (pageCount >= maxPages) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `Auto-pagination stopped at ${maxPages} pages for safety. Consider using smaller page sizes or manual pagination.`);
                        }
                        // Add all customers to returnData
                        allCustomers.forEach((customer) => {
                            returnData.push({
                                ...customer,
                                _totalCustomers: totalCustomers,
                                _autoPaginated: true,
                                _totalPages: pageCount,
                                _pageSize: pageSize,
                                _totalRecords: allCustomers.length,
                                _paginationInfo: `Fetched ${allCustomers.length} records across ${pageCount} pages`,
                            });
                        });
                    }
                    else {
                        // Single page request (original behavior)
                        const variables = {};
                        if (queryParameters.email)
                            variables.email = queryParameters.email;
                        if (queryParameters.from_date)
                            variables.from_date = new Date(queryParameters.from_date).toISOString().split('T')[0];
                        if (queryParameters.to_date)
                            variables.to_date = new Date(queryParameters.to_date).toISOString().split('T')[0];
                        if (queryParameters.date_type)
                            variables.date_type = queryParameters.date_type;
                        if (queryParameters.limit)
                            variables.limit = queryParameters.limit;
                        if (queryParameters.offset)
                            variables.offset = queryParameters.offset;
                        const responseData = await this.helpers.request({
                            method: 'POST',
                            url: `${baseUrl}/api/`,
                            headers: {
                                'Authorization': `Bearer ${accessToken}`,
                                'Content-Type': 'application/json',
                            },
                            body: {
                                query: query.trim(),
                                variables,
                            },
                            json: true,
                        });
                        // Handle GraphQL response
                        if (responseData && responseData.data && responseData.data.customers) {
                            const customers = responseData.data.customers.customers;
                            totalCustomers = responseData.data.customers.totalCustomers;
                            // Add each customer to returnData
                            if (Array.isArray(customers)) {
                                customers.forEach((customer) => {
                                    returnData.push({
                                        ...customer,
                                        _totalCustomers: totalCustomers,
                                    });
                                });
                            }
                        }
                        else if (responseData && responseData.errors) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                        }
                        else {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                        }
                    }
                }
                if (resource === 'customer' && operation === 'getUserBasket') {
                    const user_id = this.getNodeParameter('userBasket_user_id', i);
                    if (!user_id)
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'User ID is required');
                    const query = `query getUserBasket( $user_id: Int!) { getUserBasket( user_id: $user_id ) { baskets { basket_id user_id cart_detail cart_count date } totalBaskets } }`;
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
                        body: { query, variables: { user_id } },
                        json: true,
                    });
                    if (responseData && responseData.data && responseData.data.getUserBasket) {
                        const baskets = responseData.data.getUserBasket.baskets || [];
                        const totalBaskets = responseData.data.getUserBasket.totalBaskets;
                        if (Array.isArray(baskets)) {
                            for (const basket of baskets)
                                returnData.push({ ...basket, _totalBaskets: totalBaskets });
                        }
                        else if (baskets) {
                            returnData.push({ ...baskets, _totalBaskets: totalBaskets });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'order' && operation === 'get') {
                    // Get single order by ID
                    const orderId = this.getNodeParameter('orderId', i);
                    const orderFieldsSelected = this.getNodeParameter('orderFields', i);
                    const customerFieldsSelected = this.getNodeParameter('customerFieldsGet', i);
                    const productFieldsSelected = this.getNodeParameter('productFieldsGet', i);
                    const blindDetailFieldsSelected = this.getNodeParameter('blindDetailFieldsGet', i);
                    const deliveryDetailFieldsSelected = this.getNodeParameter('deliveryDetailFieldsGet', i);
                    const billingDetailFieldsSelected = this.getNodeParameter('billingDetailFieldsGet', i);
                    const shipmentDetailFieldsSelected = this.getNodeParameter('shipmentDetailFieldsGet', i);
                    // Filter out special options and separators
                    const orderFields = orderFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const customerFields = customerFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t');
                    const productFields = productFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t');
                    const blindDetailFields = blindDetailFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t');
                    const deliveryDetailFields = deliveryDetailFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t');
                    const billingDetailFields = billingDetailFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t');
                    const shipmentDetailFields = shipmentDetailFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t');
                    // Build the GraphQL query with nested response structure
                    const query = `
					query orders ($orders_id: Int) {
						orders (orders_id: $orders_id) {
							orders {
								${orderFields}
								${customerFields ? `customer { ${customerFields} }` : ''}
								${productFields ? `product { ${productFields} }` : ''}
								${blindDetailFields ? `blind_detail { ${blindDetailFields} }` : ''}
								${deliveryDetailFields ? `delivery_detail { ${deliveryDetailFields} }` : ''}
								${billingDetailFields ? `billing_detail { ${billingDetailFields} }` : ''}
								${shipmentDetailFields ? `shipment_detail { ${shipmentDetailFields} }` : ''}
							}
							totalOrders
						}
					}
				`;
                    const variables = { orders_id: parseInt(orderId) };
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    if (responseData && responseData.data && responseData.data.orders) {
                        const orders = responseData.data.orders.orders;
                        if (Array.isArray(orders) && orders.length > 0) {
                            returnData.push(orders[0]);
                        }
                        else {
                            returnData.push({
                                error: 'No order found with this ID',
                                orderId,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'order' && operation === 'getAll') {
                    // Get many orders
                    const queryParameters = this.getNodeParameter('queryParameters', i);
                    const orderFieldsSelected = this.getNodeParameter('orderFieldsGetAll', i);
                    const customerFieldsSelected = this.getNodeParameter('customerFieldsGetAll', i);
                    const productFieldsSelected = this.getNodeParameter('productFieldsGetAll', i);
                    const blindDetailFieldsSelected = this.getNodeParameter('blindDetailFieldsGetAll', i);
                    const deliveryDetailFieldsSelected = this.getNodeParameter('deliveryDetailFieldsGetAll', i);
                    const billingDetailFieldsSelected = this.getNodeParameter('billingDetailFieldsGetAll', i);
                    const shipmentDetailFieldsSelected = this.getNodeParameter('shipmentDetailFieldsGetAll', i);
                    const fetchAllPages = this.getNodeParameter('fetchAllPages', i) || false;
                    const pageSize = Math.min(queryParameters.pageSize || 250, 250); // Max 250 (API hard limit)
                    const pageDelay = Math.max(queryParameters.pageDelay || 50, 25); // Min 25ms, default 50ms
                    // Filter out special options and separators for each field group
                    const orderFields = orderFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const customerFields = customerFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const productFields = productFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const blindDetailFields = blindDetailFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const deliveryDetailFields = deliveryDetailFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const billingDetailFields = billingDetailFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    const shipmentDetailFields = shipmentDetailFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build the GraphQL query with nested response structure
                    const query = `
					query orders ($orders_id: Int, $orders_products_id: Int, $order_product_status: Int, $store_id: String, $from_date: String, $to_date: String, $order_status: String, $customer_id: Int, $order_type: OrdersOrderTypeEnum, $limit: Int, $offset: Int) {
						orders (orders_id: $orders_id, orders_products_id: $orders_products_id, order_product_status: $order_product_status, store_id: $store_id, from_date: $from_date, to_date: $to_date, order_status: $order_status, customer_id: $customer_id, order_type: $order_type, limit: $limit, offset: $offset) {
							orders {
								${orderFields}
								${customerFields ? `customer { ${customerFields} }` : ''}
								${productFields ? `product { ${productFields} }` : ''}
								${blindDetailFields ? `blind_detail { ${blindDetailFields} }` : ''}
								${deliveryDetailFields ? `delivery_detail { ${deliveryDetailFields} }` : ''}
								${billingDetailFields ? `billing_detail { ${billingDetailFields} }` : ''}
								${shipmentDetailFields ? `shipment_detail { ${shipmentDetailFields} }` : ''}
							}
							totalOrders
						}
					}
				`;
                    let allOrders = [];
                    let totalOrders = 0;
                    let offset = 0;
                    let hasMorePages = true;
                    if (fetchAllPages) {
                        // Auto-pagination: fetch all pages with rate limiting
                        let pageCount = 0;
                        const maxPages = 100; // Safety limit to prevent infinite loops
                        let adaptiveDelay = pageDelay;
                        while (hasMorePages && pageCount < maxPages) {
                            const requestStartTime = Date.now();
                            // Build variables with normalization and omit empty/undefined
                            const variables = { limit: pageSize, offset };
                            const qp = queryParameters || {};
                            if (qp.orders_id !== undefined && qp.orders_id !== '')
                                variables.orders_id = Number(qp.orders_id);
                            if (qp.orders_products_id !== undefined && qp.orders_products_id !== '')
                                variables.orders_products_id = Number(qp.orders_products_id);
                            if (qp.order_product_status !== undefined && qp.order_product_status !== '')
                                variables.order_product_status = Number(qp.order_product_status);
                            if (qp.store_id)
                                variables.store_id = String(qp.store_id);
                            if (qp.from_date)
                                variables.from_date = new Date(String(qp.from_date)).toISOString().split('T')[0];
                            if (qp.to_date)
                                variables.to_date = new Date(String(qp.to_date)).toISOString().split('T')[0];
                            if (qp.order_status)
                                variables.order_status = String(qp.order_status);
                            if (qp.customer_id !== undefined && qp.customer_id !== '')
                                variables.customer_id = Number(qp.customer_id);
                            if (qp.order_type)
                                variables.order_type = qp.order_type;
                            // Optional Safe Mode: reduce nested groups if first page fails with 5xx
                            const safeMode = this.getNodeParameter('safeMode', i, false) || false;
                            try {
                                const responseData = await this.helpers.request({
                                    method: 'POST',
                                    url: `${baseUrl}/api/`,
                                    headers: {
                                        'Authorization': `Bearer ${accessToken}`,
                                        'Content-Type': 'application/json',
                                    },
                                    body: {
                                        query: query.trim(),
                                        variables,
                                    },
                                    json: true,
                                });
                                if (responseData && responseData.data && responseData.data.orders) {
                                    const orders = responseData.data.orders.orders;
                                    totalOrders = responseData.data.orders.totalOrders;
                                    if (Array.isArray(orders) && orders.length > 0) {
                                        allOrders = allOrders.concat(orders);
                                        offset += pageSize;
                                        pageCount++;
                                        hasMorePages = orders.length === pageSize; // Continue if we got a full page
                                        // Adaptive delay: adjust based on response time
                                        const responseTime = Date.now() - requestStartTime;
                                        if (responseTime < 100) {
                                            // Fast response, can reduce delay
                                            adaptiveDelay = Math.max(25, adaptiveDelay * 0.8);
                                        }
                                        else if (responseTime > 500) {
                                            // Slow response, increase delay
                                            adaptiveDelay = Math.min(200, adaptiveDelay * 1.2);
                                        }
                                        // Add adaptive delay between requests
                                        if (hasMorePages) {
                                            await new Promise(resolve => setTimeout(resolve, Math.round(adaptiveDelay)));
                                        }
                                    }
                                    else {
                                        hasMorePages = false;
                                    }
                                }
                                else if (responseData && responseData.errors) {
                                    // When safeMode is enabled and this is the first page, retry without nested groups
                                    if (safeMode && pageCount === 0) {
                                        const minimalQuery = `
											query orders ($orders_id: Int, $orders_products_id: Int, $order_product_status: Int, $store_id: String, $from_date: String, $to_date: String, $order_status: String, $customer_id: Int, $order_type: OrdersOrderTypeEnum, $limit: Int, $offset: Int) {
												orders (orders_id: $orders_id, orders_products_id: $orders_products_id, order_product_status: $order_product_status, store_id: $store_id, from_date: $from_date, to_date: $to_date, order_status: $order_status, customer_id: $customer_id, order_type: $order_type, limit: $limit, offset: $offset) {
													orders {
														${orderFields}
													}
													totalOrders
												}
											}
										`;
                                        const retryResponse = await this.helpers.request({
                                            method: 'POST',
                                            url: `${baseUrl}/api/`,
                                            headers: {
                                                'Authorization': `Bearer ${accessToken}`,
                                                'Content-Type': 'application/json',
                                            },
                                            body: { query: minimalQuery.trim(), variables },
                                            json: true,
                                        });
                                        if (retryResponse && retryResponse.data && retryResponse.data.orders) {
                                            const orders = retryResponse.data.orders.orders;
                                            totalOrders = retryResponse.data.orders.totalOrders;
                                            if (Array.isArray(orders) && orders.length > 0) {
                                                allOrders = allOrders.concat(orders);
                                                offset += pageSize;
                                                pageCount++;
                                                hasMorePages = orders.length === pageSize;
                                                const responseTime = Date.now() - requestStartTime;
                                                if (responseTime < 100) {
                                                    adaptiveDelay = Math.max(25, adaptiveDelay * 0.8);
                                                }
                                                else if (responseTime > 500) {
                                                    adaptiveDelay = Math.min(1000, adaptiveDelay * 1.25);
                                                }
                                                continue;
                                            }
                                        }
                                    }
                                    throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error on page ${pageCount + 1}: ${JSON.stringify(responseData.errors)}`);
                                }
                                else {
                                    hasMorePages = false;
                                }
                            }
                            catch (error) {
                                // Handle rate limiting or server errors
                                if (error.statusCode === 429 || error.statusCode === 502 || error.statusCode === 503 || error.statusCode === 504) {
                                    // Rate limited or server error - wait longer and retry
                                    adaptiveDelay = Math.min(1000, adaptiveDelay * 2); // Increase delay on rate limit
                                    await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay
                                    continue; // Retry the same page
                                }
                                else {
                                    throw error; // Re-throw other errors
                                }
                            }
                        }
                        if (pageCount >= maxPages) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `Auto-pagination stopped at ${maxPages} pages for safety. Consider using smaller page sizes or manual pagination.`);
                        }
                        // Add all orders to returnData
                        allOrders.forEach((order) => {
                            returnData.push({
                                ...order,
                                _totalOrders: totalOrders,
                                _autoPaginated: true,
                                _totalPages: pageCount,
                                _pageSize: pageSize,
                                _totalRecords: allOrders.length,
                                _paginationInfo: `Fetched ${allOrders.length} records across ${pageCount} pages`,
                            });
                        });
                    }
                    else {
                        // Single page request (original behavior)
                        const variables = {};
                        if (queryParameters.orders_id)
                            variables.orders_id = queryParameters.orders_id;
                        if (queryParameters.orders_products_id)
                            variables.orders_products_id = queryParameters.orders_products_id;
                        if (queryParameters.order_product_status)
                            variables.order_product_status = queryParameters.order_product_status;
                        if (queryParameters.store_id)
                            variables.store_id = queryParameters.store_id;
                        if (queryParameters.from_date)
                            variables.from_date = new Date(queryParameters.from_date).toISOString().split('T')[0];
                        if (queryParameters.to_date)
                            variables.to_date = new Date(queryParameters.to_date).toISOString().split('T')[0];
                        if (queryParameters.order_status)
                            variables.order_status = queryParameters.order_status;
                        if (queryParameters.customer_id)
                            variables.customer_id = queryParameters.customer_id;
                        if (queryParameters.order_type)
                            variables.order_type = queryParameters.order_type;
                        if (queryParameters.limit)
                            variables.limit = queryParameters.limit;
                        if (queryParameters.offset)
                            variables.offset = queryParameters.offset;
                        const responseData = await this.helpers.request({
                            method: 'POST',
                            url: `${baseUrl}/api/`,
                            headers: {
                                'Authorization': `Bearer ${accessToken}`,
                                'Content-Type': 'application/json',
                            },
                            body: {
                                query: query.trim(),
                                variables,
                            },
                            json: true,
                        });
                        // Handle GraphQL response
                        if (responseData && responseData.data && responseData.data.orders) {
                            const orders = responseData.data.orders.orders;
                            totalOrders = responseData.data.orders.totalOrders;
                            // Add each order to returnData
                            if (Array.isArray(orders)) {
                                orders.forEach((order) => {
                                    returnData.push({
                                        ...order,
                                        _totalOrders: totalOrders,
                                    });
                                });
                            }
                        }
                        else if (responseData && responseData.errors) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                        }
                        else {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                        }
                    }
                }
                if (resource === 'order' && operation === 'getShipments') {
                    // Get order shipment details
                    const orderId = this.getNodeParameter('orderIdShipments', i);
                    const shipmentFieldsSelected = this.getNodeParameter('shipmentFields', i);
                    // Filter out special options and separators
                    const shipmentFields = shipmentFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t');
                    // Build the GraphQL query
                    const query = `
						query orderShipmentDetails ($orders_id: Int) {
							orderShipmentDetails (orders_id: $orders_id) {
								orderShipmentDetails {
									${shipmentFields}
								}
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables: { orders_id: orderId },
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.orderShipmentDetails) {
                        const shipmentData = responseData.data.orderShipmentDetails.orderShipmentDetails;
                        // Add shipment details to returnData
                        if (Array.isArray(shipmentData) && shipmentData.length > 0) {
                            shipmentData.forEach((shipment) => {
                                returnData.push({
                                    ...shipment,
                                    _order_id: orderId,
                                });
                            });
                        }
                        else {
                            // No shipment found
                            returnData.push({
                                message: 'No shipment details found for this order',
                                order_id: orderId,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'order' && operation === 'createShipment') {
                    // Create shipment for order
                    const orderId = this.getNodeParameter('orderIdCreate', i);
                    const shipmentId = this.getNodeParameter('shipmentId', i);
                    const trackingNumber = this.getNodeParameter('trackingNumber', i);
                    const packages = this.getNodeParameter('packages', i);
                    // Build package information array
                    const packageData = [];
                    if (packages && packages.package && Array.isArray(packages.package)) {
                        packages.package.forEach((pkg) => {
                            const opdata = [];
                            // Type assertion for nested orderProducts
                            const orderProducts = pkg.orderProducts;
                            if (orderProducts && orderProducts.product && Array.isArray(orderProducts.product)) {
                                orderProducts.product.forEach((product) => {
                                    opdata.push({
                                        opid: product.opid,
                                        qty: product.qty
                                    });
                                });
                            }
                            packageData.push({
                                weight: pkg.weight || 0,
                                length: pkg.length || 0,
                                width: pkg.width || 0,
                                height: pkg.height || 0,
                                tracking: pkg.tracking || trackingNumber,
                                opdata: opdata
                            });
                        });
                    }
                    // Build shipmentinfo structure
                    const shipmentinfo = [
                        {
                            packageinfo: packageData
                        }
                    ];
                    // Build the GraphQL mutation
                    const mutation = `
						mutation setShipment ($order_id: Int, $shipment_id: Int, $tracking_number: String, $shipmentinfo: JSON) {
							setShipment (order_id: $order_id, shipment_id: $shipment_id, tracking_number: $tracking_number, shipmentinfo: $shipmentinfo) {
								result
								message
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: mutation.trim(),
                            variables: {
                                order_id: orderId,
                                shipment_id: shipmentId,
                                tracking_number: trackingNumber,
                                shipmentinfo: shipmentinfo
                            },
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.setShipment) {
                        const result = responseData.data.setShipment;
                        returnData.push({
                            ...result,
                            _operation: 'createShipment',
                            _order_id: orderId,
                            _shipment_id: shipmentId,
                            _tracking_number: trackingNumber
                        });
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getSimple') {
                    // Get single product with simple fields
                    const productIdStr = this.getNodeParameter('productId', i);
                    // Validate Product ID is provided
                    if (!productIdStr || productIdStr.trim() === '') {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Product ID is required for Get Simple operation');
                    }
                    // Convert to number for API call
                    const productId = parseInt(productIdStr, 10);
                    if (isNaN(productId)) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Product ID must be a valid number');
                    }
                    const queryParameters = this.getNodeParameter('queryParameters', i);
                    const productFieldsSelected = this.getNodeParameter('productFieldsSimple', i);
                    // Build variables object
                    const variables = {
                        products_id: productId,
                    };
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Filter out special options and separators
                    const productFields = productFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build the GraphQL query
                    const query = `
						query products ($products_id: Int, $limit: Int, $offset: Int) {
							products (products_id: $products_id, limit: $limit, offset: $offset) {
								products {
									${productFields}
								}
								totalProducts
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.products) {
                        const products = responseData.data.products.products;
                        const totalProducts = responseData.data.products.totalProducts;
                        // Add each product to returnData
                        if (Array.isArray(products) && products.length > 0) {
                            products.forEach((product) => {
                                returnData.push({
                                    ...product,
                                    _totalProducts: totalProducts,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                error: 'No product found with this ID',
                                productId,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getManySimple') {
                    // Get many products with simple fields
                    const queryParameters = this.getNodeParameter('queryParametersManySimple', i);
                    const productFieldsSelected = this.getNodeParameter('productFieldsManySimple', i);
                    // Build variables object (no products_id for get many)
                    const variables = {};
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Filter out special options and separators
                    const productFields = productFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build the GraphQL query (no products_id parameter)
                    const query = `
						query products ($limit: Int, $offset: Int) {
							products (limit: $limit, offset: $offset) {
								products {
									${productFields}
								}
								totalProducts
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.products) {
                        const products = responseData.data.products.products;
                        const totalProducts = responseData.data.products.totalProducts;
                        // Add each product to returnData
                        if (Array.isArray(products)) {
                            products.forEach((product) => {
                                returnData.push({
                                    ...product,
                                    _totalProducts: totalProducts,
                                });
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getDetailed') {
                    // Get single product with detailed fields
                    const productIdStr = this.getNodeParameter('productIdDetailed', i);
                    // Validate Product ID is provided
                    if (!productIdStr || productIdStr.trim() === '') {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Product ID is required for Get Detailed operation');
                    }
                    // Convert to number for API call
                    const productId = parseInt(productIdStr, 10);
                    if (isNaN(productId)) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Product ID must be a valid number');
                    }
                    const queryParameters = this.getNodeParameter('queryParametersDetailed', i);
                    const productFieldsSelected = this.getNodeParameter('productFieldsDetailed', i);
                    const productSizeFieldsSelected = this.getNodeParameter('productSizeFields', i);
                    const productAdditionalOptionsFieldsSelected = this.getNodeParameter('productAdditionalOptionsFields', i);
                    // Build variables object
                    const variables = {
                        products_id: productId,
                    };
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    if (queryParameters.status !== undefined)
                        variables.status = queryParameters.status;
                    if (queryParameters.all_store !== undefined)
                        variables.all_store = queryParameters.all_store;
                    if (queryParameters.externalCatalogue !== undefined)
                        variables.externalCatalogue = queryParameters.externalCatalogue;
                    // Filter out special options and separators
                    const productFields = productFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build nested product_size fields
                    let productSizeQuery = '';
                    const validSizeFields = productSizeFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR');
                    if (validSizeFields.length > 0) {
                        const sizeFields = validSizeFields.join('\n\t\t\t\t\t\t\t\t');
                        productSizeQuery = `
						product_size {
							${sizeFields}
						}
					`;
                    }
                    // Build nested product_additional_options fields
                    let productOptionsQuery = '';
                    const validOptionsFields = productAdditionalOptionsFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR');
                    if (validOptionsFields.length > 0) {
                        const optionsFields = validOptionsFields.join('\n\t\t\t\t\t\t\t\t');
                        productOptionsQuery = `
						product_additional_options {
							${optionsFields}
						}
					`;
                    }
                    // Build the GraphQL query with nested fields
                    const query = `
					query productsDetails ($products_id: Int, $limit: Int, $offset: Int, $status: Int, $all_store: Int, $externalCatalogue: Int) {
						products_details (products_id: $products_id, limit: $limit, offset: $offset, status: $status, all_store: $all_store, externalCatalogue: $externalCatalogue) {
							products {
								${productFields}
								${productSizeQuery}
								${productOptionsQuery}
							}
							totalProducts
						}
					}
				`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.products_details) {
                        const products = responseData.data.products_details.products;
                        const totalProducts = responseData.data.products_details.totalProducts;
                        // Add each product to returnData
                        if (Array.isArray(products) && products.length > 0) {
                            products.forEach((product) => {
                                returnData.push({
                                    ...product,
                                    _totalProducts: totalProducts,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                error: 'No product found with this ID',
                                productId,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getManyDetailed') {
                    // Get many products with detailed fields
                    const queryParameters = this.getNodeParameter('queryParametersManyDetailed', i);
                    const productFieldsSelected = this.getNodeParameter('productFieldsManyDetailed', i);
                    const productSizeFieldsSelected = this.getNodeParameter('productSizeFields', i);
                    const productAdditionalOptionsFieldsSelected = this.getNodeParameter('productAdditionalOptionsFields', i);
                    // Build variables object (no products_id for get many)
                    const variables = {};
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    if (queryParameters.status !== undefined)
                        variables.status = queryParameters.status;
                    if (queryParameters.all_store !== undefined)
                        variables.all_store = queryParameters.all_store;
                    if (queryParameters.externalCatalogue !== undefined)
                        variables.externalCatalogue = queryParameters.externalCatalogue;
                    // Filter out special options and separators
                    const productFields = productFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build nested product_size fields
                    let productSizeQuery = '';
                    const validSizeFields = productSizeFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR');
                    if (validSizeFields.length > 0) {
                        const sizeFields = validSizeFields.join('\n\t\t\t\t\t\t\t\t');
                        productSizeQuery = `
						product_size {
							${sizeFields}
						}
					`;
                    }
                    // Build nested product_additional_options fields
                    let productOptionsQuery = '';
                    const validOptionsFields = productAdditionalOptionsFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR');
                    if (validOptionsFields.length > 0) {
                        const optionsFields = validOptionsFields.join('\n\t\t\t\t\t\t\t\t');
                        productOptionsQuery = `
						product_additional_options {
							${optionsFields}
						}
					`;
                    }
                    // Build the GraphQL query with nested fields (no products_id parameter)
                    const query = `
					query productsDetails ($limit: Int, $offset: Int, $status: Int, $all_store: Int, $externalCatalogue: Int) {
						products_details (limit: $limit, offset: $offset, status: $status, all_store: $all_store, externalCatalogue: $externalCatalogue) {
							products {
								${productFields}
								${productSizeQuery}
								${productOptionsQuery}
							}
							totalProducts
						}
					}
				`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.products_details) {
                        const products = responseData.data.products_details.products;
                        const totalProducts = responseData.data.products_details.totalProducts;
                        // Add each product to returnData
                        if (Array.isArray(products)) {
                            products.forEach((product) => {
                                returnData.push({
                                    ...product,
                                    _totalProducts: totalProducts,
                                });
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getCategory') {
                    // Get product category
                    const categoryIdStr = this.getNodeParameter('categoryId', i);
                    const queryParameters = this.getNodeParameter('queryParametersCategory', i);
                    const categoryFieldsSelected = this.getNodeParameter('categoryFields', i);
                    // Convert to number for API call
                    const categoryId = parseInt(categoryIdStr, 10);
                    if (isNaN(categoryId)) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Category ID must be a valid number');
                    }
                    // Build variables object
                    const variables = {
                        category_id: categoryId,
                    };
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Filter out special options and separators
                    const categoryFields = categoryFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build the GraphQL query
                    const query = `
						query product_category ($category_id: Int, $limit: Int, $offset: Int) {
							product_category (category_id: $category_id, limit: $limit, offset: $offset) {
								product_category {
									${categoryFields}
								}
								total_product_category_size
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_category) {
                        const categories = responseData.data.product_category.product_category;
                        const totalCategories = responseData.data.product_category.total_product_category_size;
                        // Add each category to returnData
                        if (Array.isArray(categories) && categories.length > 0) {
                            categories.forEach((category) => {
                                returnData.push({
                                    ...category,
                                    _totalCategories: totalCategories,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                error: 'No category found with this ID',
                                categoryId,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getManyCategories') {
                    // Get many product categories
                    const queryParameters = this.getNodeParameter('queryParametersManyCategories', i);
                    const categoryFieldsSelected = this.getNodeParameter('categoryFieldsMany', i);
                    // Build variables object
                    const variables = {};
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Filter out special options and separators
                    const categoryFields = categoryFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build the GraphQL query
                    const query = `
						query product_category ($limit: Int, $offset: Int) {
							product_category (limit: $limit, offset: $offset) {
								product_category {
									${categoryFields}
								}
								total_product_category_size
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_category) {
                        const categories = responseData.data.product_category.product_category;
                        const totalCategories = responseData.data.product_category.total_product_category_size;
                        // Add each category to returnData
                        if (Array.isArray(categories)) {
                            categories.forEach((category) => {
                                returnData.push({
                                    ...category,
                                    _totalCategories: totalCategories,
                                });
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getStock') {
                    // Get product stock information
                    const productIdStr = this.getNodeParameter('productIdStock', i);
                    const queryParameters = this.getNodeParameter('queryParametersStock', i);
                    const stockFieldsSelected = this.getNodeParameter('stockFields', i);
                    // Convert to number for API call
                    const productId = parseInt(productIdStr, 10);
                    if (isNaN(productId)) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Product ID must be a valid number');
                    }
                    // Build variables object
                    const variables = {
                        product_id: productId,
                    };
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Filter out special options and separators
                    const stockFields = stockFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build the GraphQL query
                    const query = `
						query productStocks ($product_id: Int!, $limit: Int, $offset: Int) {
							productStocks (product_id: $product_id, limit: $limit, offset: $offset) {
								productStocks {
									${stockFields}
								}
								totalProductStocks
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.productStocks) {
                        const stocks = responseData.data.productStocks.productStocks;
                        const totalStocks = responseData.data.productStocks.totalProductStocks;
                        // Add each stock record to returnData
                        if (Array.isArray(stocks) && stocks.length > 0) {
                            stocks.forEach((stock) => {
                                returnData.push({
                                    ...stock,
                                    _totalStocks: totalStocks,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                error: 'No stock records found for this product',
                                productId,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'updateStock') {
                    // Update product stock
                    const identifierType = this.getNodeParameter('stockIdentifierType', i);
                    const stockAction = this.getNodeParameter('stockAction', i);
                    const stockUpdateFields = this.getNodeParameter('stockUpdateFields', i);
                    // Build variables object
                    const variables = {
                        action: stockAction,
                        input: {},
                    };
                    // Set identifier (stock_id or product_sku)
                    if (identifierType === 'stock_id') {
                        const stockIdStr = this.getNodeParameter('stockId', i);
                        // Convert to number for API call
                        const stockId = parseInt(stockIdStr, 10);
                        if (isNaN(stockId)) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Stock ID must be a valid number');
                        }
                        variables.stock_id = stockId;
                    }
                    else {
                        const productSku = this.getNodeParameter('productSku', i);
                        variables.product_sku = productSku;
                    }
                    // Build input object
                    const input = {};
                    if (stockUpdateFields.stock_quantity !== undefined) {
                        input.stock_quantity = stockUpdateFields.stock_quantity;
                    }
                    if (stockUpdateFields.comment !== undefined) {
                        input.comment = stockUpdateFields.comment;
                    }
                    variables.input = input;
                    // Build the GraphQL mutation
                    const mutation = `
						mutation updateProductStock ($stock_id: Int, $product_sku: String, $action: UpdateProductStockActionEnum!, $input: UpdateProductStockInput!) {
							updateProductStock (stock_id: $stock_id, product_sku: $product_sku, action: $action, input: $input) {
								result
								message
								stock_id
								stock_quantity
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: mutation.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.updateProductStock) {
                        const result = responseData.data.updateProductStock;
                        returnData.push({
                            ...result,
                            _operation: 'updateStock',
                            _action: stockAction,
                            _identifierType: identifierType,
                        });
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                // ==================== PRODUCT: GET MASTER OPTIONS ====================
                if (resource === 'product' && operation === 'getMasterOptions') {
                    // Get product master options
                    const masterOptionIdStr = this.getNodeParameter('masterOptionId', i);
                    const selectedFields = this.getNodeParameter('masterOptionsFields', i);
                    // Validate Master Option ID is provided
                    if (!masterOptionIdStr || masterOptionIdStr.trim() === '') {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Master Option ID is required for Get Master Options operation');
                    }
                    // Convert to number for API call
                    const masterOptionId = parseInt(masterOptionIdStr, 10);
                    if (isNaN(masterOptionId)) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Master Option ID must be a valid number');
                    }
                    // Build variables object
                    const variables = {
                        master_option_id: masterOptionId,
                    };
                    // Build fields string from selected fields
                    const fieldsString = selectedFields
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t');
                    if (!fieldsString) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Select at least one Master Options Field');
                    }
                    // Build the GraphQL query for product master options
                    const query = `
						query product_master_options ($master_option_id: Int!) {
							product_master_options (master_option_id: $master_option_id) {
								product_master_options {
									${fieldsString}
								}
								total_product_master_options
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_master_options) {
                        const response = responseData.data.product_master_options;
                        const masterOptions = response.product_master_options;
                        if (Array.isArray(masterOptions)) {
                            masterOptions.forEach((option) => {
                                returnData.push({
                                    ...option,
                                    _operation: 'getMasterOptions',
                                    _masterOptionId: masterOptionId,
                                    _total: response.total_product_master_options,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                ...masterOptions,
                                _operation: 'getMasterOptions',
                                _masterOptionId: masterOptionId,
                                _total: response.total_product_master_options,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getManyMasterOptions') {
                    // Get master options for many products
                    const queryParameters = this.getNodeParameter('queryParametersManyMasterOptions', i);
                    const selectedFields = this.getNodeParameter('masterOptionsFieldsMany', i);
                    // Build variables object
                    const variables = {};
                    if (queryParameters.master_option_id)
                        variables.master_option_id = parseInt(queryParameters.master_option_id, 10);
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Build fields string from selected fields
                    const fieldsString = selectedFields
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t');
                    if (!fieldsString) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Select at least one Master Options Field');
                    }
                    // Build the GraphQL query for many product master options
                    const query = `
					query product_master_options ($master_option_id: Int, $limit: Int, $offset: Int) {
						product_master_options (master_option_id: $master_option_id, limit: $limit, offset: $offset) {
							product_master_options {
								${fieldsString}
							}
							total_product_master_options
						}
					}
				`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_master_options) {
                        const response = responseData.data.product_master_options;
                        const masterOptions = response.product_master_options;
                        if (Array.isArray(masterOptions)) {
                            masterOptions.forEach((option) => {
                                returnData.push({
                                    ...option,
                                    _operation: 'getManyMasterOptions',
                                    _total: response.total_product_master_options,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                ...masterOptions,
                                _operation: 'getManyMasterOptions',
                                _total: response.total_product_master_options,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                // ==================== PRODUCT: GET OPTIONS RULES ====================
                if (resource === 'product' && operation === 'getOptionsRules') {
                    // Get product options rules
                    const ruleIdStr = this.getNodeParameter('ruleId', i);
                    const optionsRulesFieldsSelected = this.getNodeParameter('optionsRulesFields', i);
                    // Validate Rule ID is provided
                    if (!ruleIdStr || ruleIdStr.trim() === '') {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Rule ID is required for Get Options Rules operation');
                    }
                    // Convert to number for API call
                    const ruleId = parseInt(ruleIdStr, 10);
                    if (isNaN(ruleId)) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Rule ID must be a valid number');
                    }
                    // Build variables object
                    const variables = {
                        rule_id: ruleId,
                    };
                    const optionsRulesFields = optionsRulesFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t\t');
                    if (!optionsRulesFields) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Select at least one Options Rules Field');
                    }
                    // Build the GraphQL query for product options rules
                    const query = `
						query product_option_rules ($rule_id: Int!) {
							product_option_rules (rule_id: $rule_id) {
								product_option_rules {
									${optionsRulesFields}
								}
								total_product_option_rules
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_option_rules) {
                        const response = responseData.data.product_option_rules;
                        const optionsRules = response.product_option_rules;
                        if (Array.isArray(optionsRules)) {
                            optionsRules.forEach((rule) => {
                                returnData.push({
                                    ...rule,
                                    _operation: 'getOptionsRules',
                                    _ruleId: ruleId,
                                    _total: response.total_product_option_rules,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                ...optionsRules,
                                _operation: 'getOptionsRules',
                                _ruleId: ruleId,
                                _total: response.total_product_option_rules,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getManyOptionsRules') {
                    // Get options rules for many products
                    const queryParameters = this.getNodeParameter('queryParametersManyOptionsRules', i);
                    const optionsRulesFieldsSelected = this.getNodeParameter('optionsRulesFieldsMany', i);
                    // Build variables object
                    const variables = {};
                    if (queryParameters.rule_id) {
                        const parsedRuleId = parseInt(queryParameters.rule_id, 10);
                        if (!isNaN(parsedRuleId))
                            variables.rule_id = parsedRuleId;
                    }
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    const optionsRulesFields = optionsRulesFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t\t');
                    if (!optionsRulesFields) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Select at least one Options Rules Field');
                    }
                    // Build the GraphQL query for many product options rules
                    const query = `
					query product_option_rules ($rule_id: Int, $limit: Int, $offset: Int) {
						product_option_rules (rule_id: $rule_id, limit: $limit, offset: $offset) {
							product_option_rules {
								${optionsRulesFields}
							}
							total_product_option_rules
						}
					}
				`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_option_rules) {
                        const response = responseData.data.product_option_rules;
                        const optionsRules = response.product_option_rules;
                        if (Array.isArray(optionsRules)) {
                            optionsRules.forEach((rule) => {
                                returnData.push({
                                    ...rule,
                                    _operation: 'getManyOptionsRules',
                                    _total: response.total_product_option_rules,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                ...optionsRules,
                                _operation: 'getManyOptionsRules',
                                _total: response.total_product_option_rules,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                // ==================== PRODUCT: GET PRICES ====================
                if (resource === 'product' && operation === 'getPrices') {
                    // Get product pricing information
                    const productUuidStr = this.getNodeParameter('productIdPrices', i);
                    const pricesFieldsSelected = this.getNodeParameter('pricesFields', i);
                    // Validate Product UUID is provided
                    if (!productUuidStr || productUuidStr.trim() === '') {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Product UUID is required for Get Product Prices operation');
                    }
                    // Build variables object
                    const variables = {
                        product_uuid: productUuidStr,
                    };
                    const pricesFields = pricesFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t\t');
                    if (!pricesFields) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Select at least one Prices Field');
                    }
                    // Build the GraphQL query for product prices
                    const query = `
					query product_price ($product_uuid: String!) {
						product_price (product_uuid: $product_uuid) {
							product_price {
								${pricesFields}
							}
							total_product_price
						}
					}
				`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_price) {
                        const response = responseData.data.product_price;
                        const productPrices = response.product_price;
                        const totalProductPrice = response.total_product_price;
                        if (Array.isArray(productPrices)) {
                            productPrices.forEach((price) => {
                                returnData.push({
                                    ...price,
                                    _operation: 'getPrices',
                                    _productUuid: productUuidStr,
                                    _totalProductPrice: totalProductPrice,
                                });
                            });
                        }
                        else if (productPrices) {
                            returnData.push({
                                ...productPrices,
                                _operation: 'getPrices',
                                _productUuid: productUuidStr,
                                _totalProductPrice: totalProductPrice,
                            });
                        }
                        else {
                            returnData.push({
                                _operation: 'getPrices',
                                _productUuid: productUuidStr,
                                _totalProductPrice: totalProductPrice,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getManyPrices') {
                    // Get prices for many products
                    const queryParameters = this.getNodeParameter('queryParametersManyPrices', i);
                    const pricesFieldsSelected = this.getNodeParameter('pricesFieldsMany', i);
                    // Build variables object
                    const variables = {};
                    if (queryParameters.product_uuid)
                        variables.product_uuid = queryParameters.product_uuid;
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    const pricesFields = pricesFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t\t');
                    if (!pricesFields) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Select at least one Prices Field');
                    }
                    // Build the GraphQL query for many product prices
                    const query = `
					query product_price ($product_uuid: String, $limit: Int, $offset: Int) {
						product_price (product_uuid: $product_uuid, limit: $limit, offset: $offset) {
							product_price {
								${pricesFields}
							}
							total_product_price
						}
					}
				`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_price) {
                        const response = responseData.data.product_price;
                        const productPrices = response.product_price;
                        const totalProductPrice = response.total_product_price;
                        if (Array.isArray(productPrices)) {
                            productPrices.forEach((price) => {
                                returnData.push({
                                    ...price,
                                    _operation: 'getManyPrices',
                                    _totalProductPrice: totalProductPrice,
                                });
                            });
                        }
                        else if (productPrices) {
                            returnData.push({
                                ...productPrices,
                                _operation: 'getManyPrices',
                                _totalProductPrice: totalProductPrice,
                            });
                        }
                        else {
                            returnData.push({
                                _operation: 'getManyPrices',
                                _totalProductPrice: totalProductPrice,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                // ==================== PRODUCT: GET OPTION PRICES ====================
                if (resource === 'product' && operation === 'getOptionPrices') {
                    // Get product option pricing information
                    const attrIdStr = this.getNodeParameter('productIdOptionPrices', i);
                    const optionPricesFieldsSelected = this.getNodeParameter('optionPricesFields', i);
                    // Validate Attribute ID is provided
                    if (!attrIdStr || attrIdStr.trim() === '') {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Attribute ID is required for Get Product Option Prices operation');
                    }
                    // Convert to number for API call
                    const attrId = parseInt(attrIdStr, 10);
                    if (isNaN(attrId)) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Attribute ID must be a valid number');
                    }
                    // Build variables object
                    const variables = {
                        attr_id: attrId,
                    };
                    const optionPricesFields = optionPricesFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t\t');
                    if (!optionPricesFields) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Select at least one Option Prices Field');
                    }
                    // Build the GraphQL query for product option prices
                    const query = `
						query product_options_price ($attr_id: Int!) {
							product_options_price (attr_id: $attr_id) {
								product_options_price {
									${optionPricesFields}
								}
								total_product_option_price
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_options_price) {
                        const response = responseData.data.product_options_price;
                        const optionPrices = response.product_options_price;
                        if (Array.isArray(optionPrices)) {
                            optionPrices.forEach((price) => {
                                returnData.push({
                                    ...price,
                                    _operation: 'getOptionPrices',
                                    _attrId: attrId,
                                    _total: response.total_product_option_price,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                ...optionPrices,
                                _operation: 'getOptionPrices',
                                _attrId: attrId,
                                _total: response.total_product_option_price,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getManyOptionPrices') {
                    // Get option prices for many products
                    const queryParameters = this.getNodeParameter('queryParametersManyOptionPrices', i);
                    const optionPricesFieldsSelected = this.getNodeParameter('optionPricesFieldsMany', i);
                    // Build variables object
                    const variables = {};
                    if (queryParameters.attr_id) {
                        const parsedAttrId = parseInt(queryParameters.attr_id, 10);
                        if (!isNaN(parsedAttrId))
                            variables.attr_id = parsedAttrId;
                    }
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    const optionPricesFields = optionPricesFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t\t\t');
                    if (!optionPricesFields) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Select at least one Option Prices Field');
                    }
                    // Build the GraphQL query for many product option prices
                    const query = `
					query product_options_price ($attr_id: Int, $limit: Int, $offset: Int) {
						product_options_price (attr_id: $attr_id, limit: $limit, offset: $offset) {
							product_options_price {
								${optionPricesFields}
							}
							total_product_option_price
						}
					}
				`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.product_options_price) {
                        const response = responseData.data.product_options_price;
                        const optionPrices = response.product_options_price;
                        if (Array.isArray(optionPrices)) {
                            optionPrices.forEach((price) => {
                                returnData.push({
                                    ...price,
                                    _operation: 'getManyOptionPrices',
                                    _total: response.total_product_option_price,
                                });
                            });
                        }
                        else {
                            returnData.push({
                                ...optionPrices,
                                _operation: 'getManyOptionPrices',
                                _total: response.total_product_option_price,
                            });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                // ==================== PRODUCT: GET FAQS ====================
                if (resource === 'product' && operation === 'getFAQs') {
                    // Get frequently asked questions
                    const faqId = this.getNodeParameter('faqId', i);
                    const queryParameters = this.getNodeParameter('queryParametersFAQs', i);
                    const selectedFields = this.getNodeParameter('faqFields', i, []);
                    // Build variables object
                    const variables = {};
                    variables.faq_id = faqId; // Required field
                    if (queryParameters.faqcat_id)
                        variables.faqcat_id = queryParameters.faqcat_id;
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Build fields string from selected fields
                    const fieldsString = selectedFields.length > 0 ? selectedFields.join('\n\t\t\t\t\t\t') : 'faq_id\n\t\t\t\t\t\tfaqcat_id\n\t\t\t\t\t\tstatus\n\t\t\t\t\t\tsort_order\n\t\t\t\t\t\tfaq_type\n\t\t\t\t\t\tfaq_question\n\t\t\t\t\t\tfaq_answer\n\t\t\t\t\t\tfaq_category_name\n\t\t\t\t\t\tproduct_ids\n\t\t\t\t\t\tcategory_ids';
                    // Build the GraphQL query for FAQs
                    const query = `
						query faq ($faq_id: Int, $faqcat_id: Int, $limit: Int, $offset: Int) {
							faq (faq_id: $faq_id, faqcat_id: $faqcat_id, limit: $limit, offset: $offset) {
								faq {
									${fieldsString}
								}
								totalFaq
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.faq) {
                        const faqData = responseData.data.faq;
                        if (faqData && faqData.faq) {
                            const faqs = faqData.faq;
                            if (Array.isArray(faqs)) {
                                faqs.forEach((faq) => {
                                    returnData.push({
                                        ...faq,
                                        totalFaq: faqData.totalFaq,
                                        _operation: 'getFAQs',
                                    });
                                });
                            }
                            else {
                                returnData.push({
                                    ...faqs,
                                    totalFaq: faqData.totalFaq,
                                    _operation: 'getFAQs',
                                });
                            }
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getManyFAQs') {
                    // Get many FAQs
                    const queryParameters = this.getNodeParameter('queryParametersManyFAQs', i);
                    const selectedFields = this.getNodeParameter('faqFieldsMany', i, []);
                    const fetchAllPages = this.getNodeParameter('fetchAllPagesFAQs', i, false);
                    // Build variables object
                    const variables = {};
                    if (queryParameters.faq_id)
                        variables.faq_id = queryParameters.faq_id;
                    if (queryParameters.faqcat_id)
                        variables.faqcat_id = queryParameters.faqcat_id;
                    // Set pagination parameters
                    let limit = typeof queryParameters.limit === 'number' ? queryParameters.limit : 50;
                    let offset = typeof queryParameters.offset === 'number' ? queryParameters.offset : 0;
                    if (fetchAllPages) {
                        // For fetch all pages, start with a reasonable limit and we'll loop
                        limit = 100; // Use a higher limit for efficiency
                        offset = 0;
                    }
                    else {
                        // Use user-specified limit/offset
                        if (queryParameters.limit)
                            variables.limit = queryParameters.limit;
                        if (queryParameters.offset)
                            variables.offset = queryParameters.offset;
                    }
                    // Build fields string from selected fields
                    const fieldsString = selectedFields.length > 0 ? selectedFields.join('\n\t\t\t\t\t\t') : 'faq_id\n\t\t\t\t\t\tfaqcat_id\n\t\t\t\t\t\tstatus\n\t\t\t\t\t\tsort_order\n\t\t\t\t\t\tfaq_type\n\t\t\t\t\t\tfaq_question\n\t\t\t\t\t\tfaq_answer\n\t\t\t\t\t\tfaq_category_name\n\t\t\t\t\t\tproduct_ids\n\t\t\t\t\t\tcategory_ids';
                    // Build the GraphQL query for many FAQs
                    const query = `
				query faq ($faq_id: Int, $faqcat_id: Int, $limit: Int, $offset: Int) {
					faq (faq_id: $faq_id, faqcat_id: $faqcat_id, limit: $limit, offset: $offset) {
						faq {
							${fieldsString}
						}
						totalFaq
					}
				}
			`;
                    // Handle pagination
                    let currentOffset = offset;
                    let hasMoreData = true;
                    let totalFetched = 0;
                    while (hasMoreData) {
                        // Set current pagination variables
                        const currentVariables = { ...variables };
                        if (!fetchAllPages) {
                            // For single page, use user-specified limit/offset
                            currentVariables.limit = queryParameters.limit || 50;
                            currentVariables.offset = queryParameters.offset || 0;
                        }
                        else {
                            // For fetch all pages, use our pagination variables
                            currentVariables.limit = limit;
                            currentVariables.offset = currentOffset;
                        }
                        // Make the GraphQL request
                        const responseData = await this.helpers.request({
                            method: 'POST',
                            url: `${baseUrl}/api/`,
                            headers: {
                                'Authorization': `Bearer ${accessToken}`,
                                'Content-Type': 'application/json',
                            },
                            body: {
                                query: query.trim(),
                                variables: currentVariables,
                            },
                            json: true,
                        });
                        // Handle GraphQL response
                        if (responseData && responseData.data && responseData.data.faq) {
                            const faqData = responseData.data.faq;
                            if (faqData && faqData.faq) {
                                const faqs = faqData.faq;
                                if (Array.isArray(faqs)) {
                                    faqs.forEach((faq) => {
                                        returnData.push({
                                            ...faq,
                                            totalFaq: faqData.totalFaq,
                                            _operation: 'getManyFAQs',
                                        });
                                    });
                                    totalFetched += faqs.length;
                                }
                                else {
                                    returnData.push({
                                        ...faqs,
                                        totalFaq: faqData.totalFaq,
                                        _operation: 'getManyFAQs',
                                    });
                                    totalFetched += 1;
                                }
                            }
                        }
                        else if (responseData && responseData.errors) {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                        }
                        else {
                            throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                        }
                        // Check if we should continue pagination
                        if (fetchAllPages) {
                            // Continue if we got results and haven't reached the total
                            const totalFaq = typeof ((_b = (_a = responseData === null || responseData === void 0 ? void 0 : responseData.data) === null || _a === void 0 ? void 0 : _a.faq) === null || _b === void 0 ? void 0 : _b.totalFaq) === 'number' ? responseData.data.faq.totalFaq : 0;
                            hasMoreData = totalFetched > 0 && totalFetched < totalFaq;
                            if (hasMoreData) {
                                currentOffset += limit;
                            }
                        }
                        else {
                            // Single page request, break after first iteration
                            hasMoreData = false;
                        }
                    }
                }
                if (resource === 'status' && operation === 'getStatus') {
                    // Get single status by ID
                    const processStatusIdStr = this.getNodeParameter('processStatusId', i);
                    const queryParameters = this.getNodeParameter('queryParametersStatus', i);
                    const statusFieldsSelected = this.getNodeParameter('statusFields', i);
                    // Convert to number for API call
                    const processStatusId = parseInt(processStatusIdStr, 10);
                    if (isNaN(processStatusId)) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Process Status ID must be a valid number');
                    }
                    // Build variables object
                    const variables = {
                        process_status_id: processStatusId,
                    };
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Filter out special options and separators
                    const statusFields = statusFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build the GraphQL query
                    const query = `
						query orderStatus ($process_status_id: Int, $limit: Int, $offset: Int) {
							orderStatus (process_status_id: $process_status_id, limit: $limit, offset: $offset) {
								orderStatus {
									${statusFields}
								}
								totalOrderStatus
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response
                    if (responseData && responseData.data && responseData.data.orderStatus) {
                        const statuses = responseData.data.orderStatus.orderStatus;
                        statuses.forEach((status) => {
                            returnData.push({
                                ...status,
                                _totalStatuses: responseData.data.orderStatus.totalOrderStatus,
                                _operation: 'getStatus',
                            });
                        });
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'status' && operation === 'getManyStatus') {
                    // Get many statuses with optional filtering
                    const queryParameters = this.getNodeParameter('queryParametersManyStatus', i);
                    const statusTypeFilter = this.getNodeParameter('statusTypeFilter', i);
                    const statusFieldsSelected = this.getNodeParameter('statusFieldsMany', i);
                    // Build variables object
                    const variables = {};
                    if (queryParameters.limit)
                        variables.limit = queryParameters.limit;
                    if (queryParameters.offset)
                        variables.offset = queryParameters.offset;
                    // Filter out special options and separators
                    const statusFields = statusFieldsSelected
                        .filter(field => !field.startsWith('SELECT_ALL') && !field.startsWith('DESELECT_ALL') && field !== 'SEPARATOR')
                        .join('\n\t\t\t\t\t\t\t');
                    // Build the GraphQL query
                    const query = `
						query orderStatus ($limit: Int, $offset: Int) {
							orderStatus (limit: $limit, offset: $offset) {
								orderStatus {
									${statusFields}
								}
								totalOrderStatus
							}
						}
					`;
                    // Make the GraphQL request
                    const responseData = await this.helpers.request({
                        method: 'POST',
                        url: `${baseUrl}/api/`,
                        headers: {
                            'Authorization': `Bearer ${accessToken}`,
                            'Content-Type': 'application/json',
                        },
                        body: {
                            query: query.trim(),
                            variables,
                        },
                        json: true,
                    });
                    // Handle GraphQL response and apply post-filtering
                    if (responseData && responseData.data && responseData.data.orderStatus) {
                        let statuses = responseData.data.orderStatus.orderStatus;
                        // Apply status type filter (post-filtering)
                        if (statusTypeFilter !== 'both') {
                            const filterType = statusTypeFilter === 'order' ? 'Order' : 'Product';
                            statuses = statuses.filter((status) => {
                                return status.status_type === filterType;
                            });
                        }
                        statuses.forEach((status) => {
                            returnData.push({
                                ...status,
                                _totalStatuses: responseData.data.orderStatus.totalOrderStatus,
                                _filteredBy: statusTypeFilter,
                                _operation: 'getManyStatus',
                            });
                        });
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getMasterOptionTag') {
                    const variables = {};
                    const master_option_tag_id = this.getNodeParameter('masterOptionTag_master_option_tag_id', i);
                    const limit = this.getNodeParameter('masterOptionTag_limit', i);
                    const offset = this.getNodeParameter('masterOptionTag_offset', i);
                    if (master_option_tag_id)
                        variables.master_option_tag_id = master_option_tag_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query getMasterOptionTag ($master_option_tag_id: Int, $limit: Int, $offset: Int) { getMasterOptionTag (master_option_tag_id: $master_option_tag_id, limit: $limit, offset: $offset) { masterOptionTag { master_option_tag_id master_option_tag_name } totalMasterOptionTag } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.getMasterOptionTag) {
                        const rows = responseData.data.getMasterOptionTag.masterOptionTag || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalMasterOptionTag: responseData.data.getMasterOptionTag.totalMasterOptionTag });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getOptionGroup') {
                    const variables = {};
                    const prod_add_opt_group_id = this.getNodeParameter('optionGroup_prod_add_opt_group_id', i);
                    const use_for = this.getNodeParameter('optionGroup_use_for', i);
                    const limit = this.getNodeParameter('optionGroup_limit', i);
                    const offset = this.getNodeParameter('optionGroup_offset', i);
                    if (prod_add_opt_group_id)
                        variables.prod_add_opt_group_id = prod_add_opt_group_id;
                    if (use_for)
                        variables.use_for = use_for;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query getOptionGroup ($prod_add_opt_group_id: Int,$use_for: String, $limit: Int, $offset: Int) { getOptionGroup (prod_add_opt_group_id: $prod_add_opt_group_id,use_for: $use_for, limit: $limit, offset: $offset) { optionGroup { prod_add_opt_group_id opt_group_name use_for display_style option_count is_collapse sort_order } totalOptionGroup } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.getOptionGroup) {
                        const rows = responseData.data.getOptionGroup.optionGroup || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalOptionGroup: responseData.data.getOptionGroup.totalOptionGroup });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getCustomFormula') {
                    const variables = {};
                    const formula_id = this.getNodeParameter('customFormula_formula_id', i);
                    const limit = this.getNodeParameter('customFormula_limit', i);
                    const offset = this.getNodeParameter('customFormula_offset', i);
                    if (formula_id)
                        variables.formula_id = formula_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query getCustomFormula ($formula_id: Int, $limit: Int, $offset: Int) { getCustomFormula (formula_id: $formula_id, limit: $limit, offset: $offset) { customFormula { formula_id formula_label formula_syntax } totalCustomFormula } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.getCustomFormula) {
                        const rows = responseData.data.getCustomFormula.customFormula || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalCustomFormula: responseData.data.getCustomFormula.totalCustomFormula });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'getMasterOptionRange') {
                    const variables = {};
                    const range_id = this.getNodeParameter('masterOptionRange_range_id', i);
                    const option_id = this.getNodeParameter('masterOptionRange_option_id', i);
                    const limit = this.getNodeParameter('masterOptionRange_limit', i);
                    const offset = this.getNodeParameter('masterOptionRange_offset', i);
                    if (range_id)
                        variables.range_id = range_id;
                    if (option_id)
                        variables.option_id = option_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query getMasterOptionRange ($range_id: Int, $option_id: Int, $limit: Int, $offset: Int) { getMasterOptionRange (range_id: $range_id, option_id: $option_id, limit: $limit, offset: $offset) { masterOptionRange { range_id option_id from_range to_range } totalMasterOptionRange } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.getMasterOptionRange) {
                        const rows = responseData.data.getMasterOptionRange.masterOptionRange || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalMasterOptionRange: responseData.data.getMasterOptionRange.totalMasterOptionRange });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'get_faq_category') {
                    const variables = {};
                    const faqcat_id = this.getNodeParameter('faqCategory_faqcat_id', i);
                    const status = this.getNodeParameter('faqCategory_status', i);
                    const limit = this.getNodeParameter('faqCategory_limit', i);
                    const offset = this.getNodeParameter('faqCategory_offset', i);
                    if (faqcat_id)
                        variables.faqcat_id = faqcat_id;
                    if (status)
                        variables.status = status;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query get_faq_category($faqcat_id: Int, $status: Int, $limit: Int, $offset: Int) { get_faq_category(faqcat_id: $faqcat_id, status: $status, limit: $limit, offset: $offset) { faq_category { faqcat_id status sort_order faq_category_name } totalFaqCategory } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.get_faq_category) {
                        const rows = responseData.data.get_faq_category.faq_category || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _totalFaqCategory: responseData.data.get_faq_category.totalFaqCategory });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'product_additional_options') {
                    const variables = {};
                    const products_id = this.getNodeParameter('additionalOptions_products_id', i);
                    const limit = this.getNodeParameter('additionalOptions_limit', i);
                    const offset = this.getNodeParameter('additionalOptions_offset', i);
                    if (products_id)
                        variables.products_id = products_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query product_additional_options ($products_id: Int, $limit: Int, $offset: Int) { product_additional_options (products_id: $products_id, limit: $limit, offset: $offset) { product_additional_options { prod_add_opt_id title description options_type sort_order status apply_multiplication applicable_for required price_calculate_type hire_designer_option option_key master_option_id attributes } total_product_additional_options } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.product_additional_options) {
                        const rows = responseData.data.product_additional_options.product_additional_options || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _total_product_additional_options: responseData.data.product_additional_options.total_product_additional_options });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
                if (resource === 'product' && operation === 'products_attribute_price') {
                    const variables = {};
                    const attribute_id = this.getNodeParameter('attributePrice_attribute_id', i);
                    const size_id = this.getNodeParameter('attributePrice_size_id', i);
                    const limit = this.getNodeParameter('attributePrice_limit', i);
                    const offset = this.getNodeParameter('attributePrice_offset', i);
                    if (attribute_id)
                        variables.attribute_id = attribute_id;
                    if (size_id)
                        variables.size_id = size_id;
                    if (limit)
                        variables.limit = limit;
                    if (offset)
                        variables.offset = offset;
                    const query = `query products_attribute_price($attribute_id: Int, $size_id: Int, $limit: Int, $offset: Int) { products_attribute_price(attribute_id: $attribute_id, size_id: $size_id, limit: $limit, offset: $offset) { products_attribute_price { attribute_price_id attribute_id size_id quantity quantity_to attributes_price extra_page_price } total_products_attribute_price } }`;
                    const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query, variables }, json: true });
                    if (responseData && responseData.data && responseData.data.products_attribute_price) {
                        const rows = responseData.data.products_attribute_price.products_attribute_price || [];
                        for (const row of rows) {
                            returnData.push({ ...row, _total_products_attribute_price: responseData.data.products_attribute_price.total_products_attribute_price });
                        }
                    }
                    else if (responseData && responseData.errors) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
                    }
                    else {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Unexpected response format from API');
                    }
                }
            }
            catch (error) {
                if (this.continueOnFail()) {
                    returnData.push({ error: error.message });
                    continue;
                }
                throw error;
            }
        }
        return [this.helpers.returnJsonArray(returnData)];
    }
}
exports.OnPrintShop = OnPrintShop;
