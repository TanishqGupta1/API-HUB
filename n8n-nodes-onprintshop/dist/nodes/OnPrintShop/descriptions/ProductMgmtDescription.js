"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.productMgmtFields = exports.productMgmtOperations = void 0;
exports.productMgmtOperations = [
    {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        noDataExpression: true,
        displayOptions: {
            show: {
                resource: ['productMgmt'],
            },
        },
        options: [
            { name: 'Set Product', value: 'setProduct', action: 'Create or update a product' },
            { name: 'Set Product Price', value: 'setProductPrice', action: 'Update product price' },
            { name: 'Set Product Size', value: 'setProductSize', action: 'Update product size' },
            { name: 'Set Product Pages', value: 'setProductPages', action: 'Update product pages' },
            { name: 'Set Product Category', value: 'setProductCategory', action: 'Update product category' },
            { name: 'Set Product Design', value: 'setProductDesign', action: 'Update product design links' },
            { name: 'Set Assign Options', value: 'setAssignOptions', action: 'Assign options to product' },
            { name: 'Get Additional Options', value: 'product_additional_options', action: 'Read product additional options' },
        ],
        default: 'setProduct',
    },
];
exports.productMgmtFields = [
    // setProduct
    {
        displayName: 'Title',
        name: 'title',
        type: 'string',
        required: true,
        displayOptions: {
            show: {
                resource: ['productMgmt'],
                operation: ['setProduct'],
            },
        },
        default: '',
    },
    // Common Product ID for other mutations
    {
        displayName: 'Product ID',
        name: 'productId',
        type: 'number',
        required: true,
        displayOptions: {
            show: {
                resource: ['productMgmt'],
                operation: [
                    'setProductPrice',
                    'setProductSize',
                    'setProductPages',
                    'setProductCategory',
                    'setProductDesign',
                    'setAssignOptions',
                    'product_additional_options',
                ],
            },
        },
        default: 0,
    },
    // Additional Fields
    {
        displayName: 'Additional Fields',
        name: 'additionalFields',
        type: 'collection',
        placeholder: 'Add Field',
        default: {},
        displayOptions: {
            show: {
                resource: ['productMgmt'],
                operation: [
                    'setProduct',
                    'setProductPrice',
                    'setProductSize',
                    'setProductPages',
                    'setProductCategory',
                    'setProductDesign',
                    'setAssignOptions',
                ],
            },
        },
        options: [
            { displayName: 'ID', name: 'id', type: 'number', default: 0 },
            { displayName: 'SKU', name: 'sku', type: 'string', default: '' },
            { displayName: 'Status', name: 'status', type: 'number', default: 1 },
            { displayName: 'Description', name: 'description', type: 'string', default: '' },
        ],
    },
    // Query params for product_additional_options
    {
        displayName: 'Limit',
        name: 'limit',
        type: 'number',
        displayOptions: {
            show: {
                resource: ['productMgmt'],
                operation: ['product_additional_options'],
            },
        },
        default: 10,
    },
    {
        displayName: 'Offset',
        name: 'offset',
        type: 'number',
        displayOptions: {
            show: {
                resource: ['productMgmt'],
                operation: ['product_additional_options'],
            },
        },
        default: 0,
    },
];
