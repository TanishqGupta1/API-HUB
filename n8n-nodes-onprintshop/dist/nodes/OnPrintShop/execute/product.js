"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.productExecute = void 0;
const GenericFunctions_1 = require("../GenericFunctions");
const mutations = __importStar(require("../graphql/mutations"));
const queries = __importStar(require("../graphql/queries"));
async function productExecute(index) {
    const operation = this.getNodeParameter('operation', index);
    let responseData;
    if (operation === 'setProduct') {
        const title = this.getNodeParameter('title', index);
        const additionalFields = this.getNodeParameter('additionalFields', index);
        const input = {
            title,
            ...additionalFields,
        };
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setProductMutation, { input });
    }
    else if (operation === 'setProductPrice') {
        const productId = this.getNodeParameter('productId', index);
        const additionalFields = this.getNodeParameter('additionalFields', index);
        const input = {
            products_id: productId,
            ...additionalFields,
        };
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setProductPriceMutation, { input });
    }
    else if (operation === 'setProductSize') {
        const productId = this.getNodeParameter('productId', index);
        const additionalFields = this.getNodeParameter('additionalFields', index);
        const input = {
            products_id: productId,
            ...additionalFields,
        };
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setProductSizeMutation, { input });
    }
    else if (operation === 'setProductPages') {
        const productId = this.getNodeParameter('productId', index);
        const additionalFields = this.getNodeParameter('additionalFields', index);
        const input = {
            products_id: productId,
            ...additionalFields,
        };
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setProductPagesMutation, { input });
    }
    else if (operation === 'setProductCategory') {
        const productId = this.getNodeParameter('productId', index);
        const additionalFields = this.getNodeParameter('additionalFields', index);
        const input = {
            products_id: productId,
            ...additionalFields,
        };
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setProductCategoryMutation, { input });
    }
    else if (operation === 'setProductDesign') {
        const productId = this.getNodeParameter('productId', index);
        const additionalFields = this.getNodeParameter('additionalFields', index);
        const input = {
            products_id: productId,
            ...additionalFields,
        };
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setProductDesignMutation, { input });
    }
    else if (operation === 'setAssignOptions') {
        const productId = this.getNodeParameter('productId', index);
        const additionalFields = this.getNodeParameter('additionalFields', index);
        const input = {
            products_id: productId,
            ...additionalFields,
        };
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setAssignOptionsMutation, { input });
    }
    else if (operation === 'product_additional_options') {
        const productId = this.getNodeParameter('productId', index);
        const limit = this.getNodeParameter('limit', index, 10);
        const offset = this.getNodeParameter('offset', index, 0);
        responseData = await GenericFunctions_1.opsRequest.call(this, queries.getProductAdditionalOptionsQuery, {
            product_id: productId,
            limit,
            offset,
        });
    }
    return this.helpers.returnJsonArray(responseData.data[operation]);
}
exports.productExecute = productExecute;
