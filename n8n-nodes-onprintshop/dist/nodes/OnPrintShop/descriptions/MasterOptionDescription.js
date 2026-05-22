"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.masterOptionFields = exports.masterOptionOperations = void 0;
exports.masterOptionOperations = [
    {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        noDataExpression: true,
        displayOptions: {
            show: {
                resource: ['masterOption'],
            },
        },
        options: [
            { name: 'Get Tag', value: 'getMasterOptionTag', action: 'Read master option tags' },
            { name: 'Get Option Group', value: 'getOptionGroup', action: 'Read option groups' },
            { name: 'Get Custom Formula', value: 'getCustomFormula', action: 'Read option formulas' },
            { name: 'Get Range', value: 'getMasterOptionRange', action: 'Read master option ranges' },
            { name: 'Set Option Rules', value: 'setProductOptionRules', action: 'Update master option rules' },
            { name: 'Set Custom Formula', value: 'setCustomFormula', action: 'Update option formulas' },
            { name: 'Set Option Group', value: 'setOptionGroup', action: 'Update option groups' },
            { name: 'Set Tag', value: 'setMasterOptionTag', action: 'Update master option tags' },
            { name: 'Set Attributes', value: 'setMasterOptionAttributes', action: 'Update master option attributes' },
            { name: 'Set Attribute Price', value: 'setMasterOptionAttributePrice', action: 'Update master option attribute prices' },
        ],
        default: 'getMasterOptionTag',
    },
];
exports.masterOptionFields = [
    // getMasterOptionTag
    {
        displayName: 'Tag ID',
        name: 'tagId',
        type: 'number',
        displayOptions: {
            show: {
                resource: ['masterOption'],
                operation: ['getMasterOptionTag'],
            },
        },
        default: 0,
    },
    // getOptionGroup
    {
        displayName: 'Group ID',
        name: 'groupId',
        type: 'number',
        displayOptions: {
            show: {
                resource: ['masterOption'],
                operation: ['getOptionGroup'],
            },
        },
        default: 0,
    },
    {
        displayName: 'Use For',
        name: 'useFor',
        type: 'string',
        displayOptions: {
            show: {
                resource: ['masterOption'],
                operation: ['getOptionGroup'],
            },
        },
        default: '',
    },
    // getCustomFormula
    {
        displayName: 'Formula ID',
        name: 'formulaId',
        type: 'number',
        displayOptions: {
            show: {
                resource: ['masterOption'],
                operation: ['getCustomFormula'],
            },
        },
        default: 0,
    },
    // getMasterOptionRange
    {
        displayName: 'Range ID',
        name: 'rangeId',
        type: 'number',
        displayOptions: {
            show: {
                resource: ['masterOption'],
                operation: ['getMasterOptionRange'],
            },
        },
        default: 0,
    },
    {
        displayName: 'Option ID',
        name: 'optionId',
        type: 'number',
        displayOptions: {
            show: {
                resource: ['masterOption'],
                operation: ['getMasterOptionRange'],
            },
        },
        default: 0,
    },
    // Mutations: Additional Fields
    {
        displayName: 'Additional Fields',
        name: 'additionalFields',
        type: 'collection',
        placeholder: 'Add Field',
        default: {},
        displayOptions: {
            show: {
                resource: ['masterOption'],
                operation: [
                    'setProductOptionRules',
                    'setCustomFormula',
                    'setOptionGroup',
                    'setMasterOptionTag',
                    'setMasterOptionAttributes',
                    'setMasterOptionAttributePrice',
                ],
            },
        },
        options: [
            { displayName: 'ID', name: 'id', type: 'number', default: 0 },
            { displayName: 'Title', name: 'title', type: 'string', default: '' },
            { displayName: 'Status', name: 'status', type: 'number', default: 1 },
        ],
    },
    // Common Pagination
    {
        displayName: 'Limit',
        name: 'limit',
        type: 'number',
        displayOptions: {
            show: {
                resource: ['masterOption'],
                operation: ['getMasterOptionTag', 'getOptionGroup', 'getCustomFormula', 'getMasterOptionRange'],
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
                resource: ['masterOption'],
                operation: ['getMasterOptionTag', 'getOptionGroup', 'getCustomFormula', 'getMasterOptionRange'],
            },
        },
        default: 0,
    },
];
