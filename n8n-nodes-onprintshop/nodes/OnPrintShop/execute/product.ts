import {
	IExecuteFunctions,
	INodeExecutionData,
} from 'n8n-workflow';

import { opsRequest } from '../GenericFunctions';
import * as mutations from '../graphql/mutations';
import * as queries from '../graphql/queries';

export async function productExecute(
	this: IExecuteFunctions,
	index: number,
): Promise<INodeExecutionData[]> {
	const operation = this.getNodeParameter('operation', index) as string;
	let responseData;

	if (operation === 'setProduct') {
		const title = this.getNodeParameter('title', index) as string;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		
		const input = {
			title,
			...additionalFields,
		};

		responseData = await opsRequest.call(this, mutations.setProductMutation, { input });
	} else if (operation === 'setProductPrice') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		
		const input = {
			products_id: productId,
			...additionalFields,
		};

		responseData = await opsRequest.call(this, mutations.setProductPriceMutation, { input });
	} else if (operation === 'setProductSize') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		
		const input = {
			products_id: productId,
			...additionalFields,
		};

		responseData = await opsRequest.call(this, mutations.setProductSizeMutation, { input });
	} else if (operation === 'setProductPages') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		
		const input = {
			products_id: productId,
			...additionalFields,
		};

		responseData = await opsRequest.call(this, mutations.setProductPagesMutation, { input });
	} else if (operation === 'setProductCategory') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		
		const input = {
			products_id: productId,
			...additionalFields,
		};

		responseData = await opsRequest.call(this, mutations.setProductCategoryMutation, { input });
	} else if (operation === 'setProductDesign') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		
		const input = {
			products_id: productId,
			...additionalFields,
		};

		responseData = await opsRequest.call(this, mutations.setProductDesignMutation, { input });
	} else if (operation === 'setAssignOptions') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		
		const input = {
			products_id: productId,
			...additionalFields,
		};

		responseData = await opsRequest.call(this, mutations.setAssignOptionsMutation, { input });
	} else if (operation === 'product_additional_options') {
		const productId = this.getNodeParameter('productId', index) as number;
		const limit = this.getNodeParameter('limit', index, 10) as number;
		const offset = this.getNodeParameter('offset', index, 0) as number;

		responseData = await opsRequest.call(this, queries.getProductAdditionalOptionsQuery, {
			product_id: productId,
			limit,
			offset,
		});
	}

	return this.helpers.returnJsonArray(responseData.data[operation]);
}
