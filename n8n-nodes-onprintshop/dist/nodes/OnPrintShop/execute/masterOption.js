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
exports.masterOptionExecute = void 0;
const GenericFunctions_1 = require("../GenericFunctions");
const mutations = __importStar(require("../graphql/mutations"));
const queries = __importStar(require("../graphql/queries"));
async function masterOptionExecute(index) {
    const operation = this.getNodeParameter('operation', index);
    let responseData;
    if (operation === 'getMasterOptionTag') {
        const tagId = this.getNodeParameter('tagId', index, 0);
        const limit = this.getNodeParameter('limit', index, 10);
        const offset = this.getNodeParameter('offset', index, 0);
        responseData = await GenericFunctions_1.opsRequest.call(this, queries.getMasterOptionTagQuery, { master_option_tag_id: tagId, limit, offset });
    }
    else if (operation === 'getOptionGroup') {
        const groupId = this.getNodeParameter('groupId', index, 0);
        const useFor = this.getNodeParameter('useFor', index, '');
        const limit = this.getNodeParameter('limit', index, 10);
        const offset = this.getNodeParameter('offset', index, 0);
        responseData = await GenericFunctions_1.opsRequest.call(this, queries.getOptionGroupQuery, { prod_add_opt_group_id: groupId, use_for: useFor, limit, offset });
    }
    else if (operation === 'getCustomFormula') {
        const formulaId = this.getNodeParameter('formulaId', index, 0);
        const limit = this.getNodeParameter('limit', index, 10);
        const offset = this.getNodeParameter('offset', index, 0);
        responseData = await GenericFunctions_1.opsRequest.call(this, queries.getCustomFormulaQuery, { formula_id: formulaId, limit, offset });
    }
    else if (operation === 'getMasterOptionRange') {
        const rangeId = this.getNodeParameter('rangeId', index, 0);
        const optionId = this.getNodeParameter('optionId', index, 0);
        const limit = this.getNodeParameter('limit', index, 10);
        const offset = this.getNodeParameter('offset', index, 0);
        responseData = await GenericFunctions_1.opsRequest.call(this, queries.getMasterOptionRangeQuery, { range_id: rangeId, option_id: optionId, limit, offset });
    }
    else if (operation === 'setProductOptionRules') {
        const additionalFields = this.getNodeParameter('additionalFields', index);
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setProductOptionRulesMutation, { input: additionalFields });
    }
    else if (operation === 'setCustomFormula') {
        const additionalFields = this.getNodeParameter('additionalFields', index);
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setCustomFormulaMutation, { input: additionalFields });
    }
    else if (operation === 'setOptionGroup') {
        const additionalFields = this.getNodeParameter('additionalFields', index);
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setOptionGroupMutation, { input: additionalFields });
    }
    else if (operation === 'setMasterOptionTag') {
        const additionalFields = this.getNodeParameter('additionalFields', index);
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setMasterOptionTagMutation, { input: additionalFields });
    }
    else if (operation === 'setMasterOptionAttributes') {
        const additionalFields = this.getNodeParameter('additionalFields', index);
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setMasterOptionAttributesMutation, { input: additionalFields });
    }
    else if (operation === 'setMasterOptionAttributePrice') {
        const additionalFields = this.getNodeParameter('additionalFields', index);
        responseData = await GenericFunctions_1.opsRequest.call(this, mutations.setMasterOptionAttributePriceMutation, { input: additionalFields });
    }
    return this.helpers.returnJsonArray(responseData.data[operation]);
}
exports.masterOptionExecute = masterOptionExecute;
