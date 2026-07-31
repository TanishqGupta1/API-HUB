import {
	IExecuteFunctions,
	INodeExecutionData,
} from 'n8n-workflow';

import { opsRequest } from '../GenericFunctions';
import * as mutations from '../graphql/mutations';
import * as queries from '../graphql/queries';

export async function masterOptionExecute(
	this: IExecuteFunctions,
	index: number,
): Promise<INodeExecutionData[]> {
	const operation = this.getNodeParameter('operation', index) as string;
	let responseData;

	if (operation === 'getMasterOptionTag') {
		const tagId = this.getNodeParameter('tagId', index, 0) as number;
		const limit = this.getNodeParameter('limit', index, 10) as number;
		const offset = this.getNodeParameter('offset', index, 0) as number;
		responseData = await opsRequest.call(this, queries.getMasterOptionTagQuery, { master_option_tag_id: tagId, limit, offset });
	} else if (operation === 'getOptionGroup') {
		const groupId = this.getNodeParameter('groupId', index, 0) as number;
		const useFor = this.getNodeParameter('useFor', index, '') as string;
		const limit = this.getNodeParameter('limit', index, 10) as number;
		const offset = this.getNodeParameter('offset', index, 0) as number;
		responseData = await opsRequest.call(this, queries.getOptionGroupQuery, { prod_add_opt_group_id: groupId, use_for: useFor, limit, offset });
	} else if (operation === 'getCustomFormula') {
		const formulaId = this.getNodeParameter('formulaId', index, 0) as number;
		const limit = this.getNodeParameter('limit', index, 10) as number;
		const offset = this.getNodeParameter('offset', index, 0) as number;
		responseData = await opsRequest.call(this, queries.getCustomFormulaQuery, { formula_id: formulaId, limit, offset });
	} else if (operation === 'getMasterOptionRange') {
		const rangeId = this.getNodeParameter('rangeId', index, 0) as number;
		const optionId = this.getNodeParameter('optionId', index, 0) as number;
		const limit = this.getNodeParameter('limit', index, 10) as number;
		const offset = this.getNodeParameter('offset', index, 0) as number;
		responseData = await opsRequest.call(this, queries.getMasterOptionRangeQuery, { range_id: rangeId, option_id: optionId, limit, offset });
	} else if (operation === 'setProductOptionRules') {
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		responseData = await opsRequest.call(this, mutations.setProductOptionRulesMutation, { input: additionalFields });
	} else if (operation === 'setCustomFormula') {
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		responseData = await opsRequest.call(this, mutations.setCustomFormulaMutation, { input: additionalFields });
	} else if (operation === 'setOptionGroup') {
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		responseData = await opsRequest.call(this, mutations.setOptionGroupMutation, { input: additionalFields });
	} else if (operation === 'setMasterOptionTag') {
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		responseData = await opsRequest.call(this, mutations.setMasterOptionTagMutation, { input: additionalFields });
	} else if (operation === 'setMasterOptionAttributes') {
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		responseData = await opsRequest.call(this, mutations.setMasterOptionAttributesMutation, { input: additionalFields });
	} else if (operation === 'setMasterOptionAttributePrice') {
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		responseData = await opsRequest.call(this, mutations.setMasterOptionAttributePriceMutation, { input: additionalFields });
	}

	return this.helpers.returnJsonArray(responseData.data[operation]);
}
