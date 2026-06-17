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
		const input = { title, ...additionalFields };
		responseData = await opsRequest.call(this, mutations.setProductMutation, { inputs: [input] });
	} else if (operation === 'setProductPrice') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = { products_id: productId, ...additionalFields };
		responseData = await opsRequest.call(this, mutations.setProductPriceMutation, { inputs: [input] });
	} else if (operation === 'setProductSize') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = { products_id: productId, ...additionalFields };
		responseData = await opsRequest.call(this, mutations.setProductSizeMutation, { inputs: [input] });
	} else if (operation === 'setProductPages') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = { products_id: productId, ...additionalFields };
		responseData = await opsRequest.call(this, mutations.setProductPagesMutation, { input });
	} else if (operation === 'setProductCategory') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = { products_id: productId, ...additionalFields };
		responseData = await opsRequest.call(this, mutations.setProductCategoryMutation, { inputs: [input] });
	} else if (operation === 'setProductDesign') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = { products_id: productId, ...additionalFields };
		responseData = await opsRequest.call(this, mutations.setProductDesignMutation, { input });
	} else if (operation === 'setAssignOptions') {
		const productId = this.getNodeParameter('productId', index) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = { products_id: productId, ...additionalFields };
		responseData = await opsRequest.call(this, mutations.setAssignOptionsMutation, { inputs: [input] });
	} else if (operation === 'setProductSku') {
		const productId = this.getNodeParameter('productId', index) as number;
		const skuType = this.getNodeParameter('skuType', index) as string;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = { products_id: productId, sku_type: skuType, ...additionalFields };
		responseData = await opsRequest.call(this, mutations.setProductSkuMutation, { inputs: [input] });
	} else if (operation === 'updateProductStock') {
		const productSku = this.getNodeParameter('productSku', index, '') as string;
		const stockId = this.getNodeParameter('stockId', index, 0) as number;
		const action = this.getNodeParameter('action', index) as string;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		responseData = await opsRequest.call(this, mutations.updateProductStockMutation, {
			...(productSku ? { product_sku: productSku } : {}),
			...(stockId ? { stock_id: stockId } : {}),
			action,
			input: additionalFields,
		});
	} else if (operation === 'getProductSkuMatrix') {
		const productId = this.getNodeParameter('productId', index) as number;
		const prodAddOptIds = this.getNodeParameter('prodAddOptIds', index, '') as string;
		responseData = await opsRequest.call(this, queries.getProductSkuMatrixQuery, {
			products_id: productId,
			...(prodAddOptIds ? { prod_add_opt_ids: prodAddOptIds } : {}),
		});
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
