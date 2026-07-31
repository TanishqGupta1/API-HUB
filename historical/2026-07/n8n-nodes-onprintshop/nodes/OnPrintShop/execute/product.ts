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
	} else if (operation === 'setAdditionalOption') {
		const productId = this.getNodeParameter('productId', index) as number;
		const optionsType = this.getNodeParameter('optionsType', index, 'radio') as string;
		const title = this.getNodeParameter('title', index, '') as string;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = {
			products_id: productId,
			options_type: optionsType,
			...(title ? { title } : {}),
			...additionalFields,
		};
		responseData = await opsRequest.call(this, mutations.setAdditionalOptionMutation, { inputs: [input] });
	} else if (operation === 'setAdditionalOptionAttributes') {
		const prodAddOptId = this.getNodeParameter('prodAddOptId', index) as number;
		const label = this.getNodeParameter('label', index, '') as string;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = {
			prod_add_opt_id: prodAddOptId,
			...(label ? { label } : {}),
			...additionalFields,
		};
		responseData = await opsRequest.call(this, mutations.setAdditionalOptionAttributesMutation, { inputs: [input] });
	} else if (operation === 'setProductsAttributePrice') {
		const attributeId = this.getNodeParameter('attributeId', index) as number;
		const attributesPrice = this.getNodeParameter('attributesPrice', index, 0) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		const input = {
			attribute_id: attributeId,
			// Default "any size" range so apparel callers don't need to fill them;
			// print-product callers override via additionalFields.
			size_from: 0.01,
			size_to: 99999999.99,
			...(attributesPrice ? { attributes_price: attributesPrice } : {}),
			...additionalFields,
		};
		responseData = await opsRequest.call(this, mutations.setProductsAttributePriceMutation, { inputs: [input] });
	} else if (operation === 'setProductsImageGallery') {
		const productId = this.getNodeParameter('productId', index) as number;
		const imageFilename = this.getNodeParameter('imageFilename', index) as string;
		const optimizeImg = this.getNodeParameter('optimizeImg', index, 0) as number;
		const additionalFields = this.getNodeParameter('additionalFields', index) as any;
		// One image per execution; loop the node for multi-image batches.
		const imageEntry = {
			products_large_image_name: imageFilename,
			delete: 0,
			...additionalFields,
		};
		responseData = await opsRequest.call(this, mutations.setProductsImageGalleryMutation, {
			products_id: productId,
			optimizeimg: optimizeImg,
			input: { image_arr: [imageEntry] },
		});
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
	} else if (operation === 'productCategory') {
		const categoryId = this.getNodeParameter('categoryId', index, 0) as number;
		const limit = this.getNodeParameter('productCategoryLimit', index, 50) as number;
		const offset = this.getNodeParameter('productCategoryOffset', index, 0) as number;
		responseData = await opsRequest.call(this, queries.getProductCategoryQuery, {
			...(categoryId ? { category_id: categoryId } : {}),
			limit,
			offset,
		});
	} else if (operation === 'productStocks') {
		const productId = this.getNodeParameter('productId', index) as number;
		const limit = this.getNodeParameter('limit', index, 50) as number;
		const offset = this.getNodeParameter('offset', index, 0) as number;
		responseData = await opsRequest.call(this, queries.getProductStocksQuery, {
			product_id: productId,
			limit,
			offset,
		});
	} else if (operation === 'products') {
		const productsId = this.getNodeParameter('productsListProductId', index, 0) as number;
		const limit = this.getNodeParameter('productsListLimit', index, 10) as number;
		const offset = this.getNodeParameter('productsListOffset', index, 0) as number;
		responseData = await opsRequest.call(this, queries.getProductsListQuery, {
			...(productsId ? { products_id: productsId } : {}),
			limit,
			offset,
		});
	} else if (operation === 'productsDetails') {
		const productsId = this.getNodeParameter('productsDetailsProductId', index, 0) as number;
		const limit = this.getNodeParameter('productsDetailsLimit', index, 10) as number;
		const offset = this.getNodeParameter('productsDetailsOffset', index, 0) as number;
		const status = this.getNodeParameter('productsDetailsStatus', index, 0) as number;
		const allStore = this.getNodeParameter('productsDetailsAllStore', index, 0) as number;
		const externalCatalogue = this.getNodeParameter('productsDetailsExternalCatalogue', index, 0) as number;
		// Only send filters the user actually set — sending {products_id: 0} acts
		// as a filter for product 0, not "no filter."
		responseData = await opsRequest.call(this, queries.getProductsDetailsQuery, {
			...(productsId ? { products_id: productsId } : {}),
			limit,
			offset,
			...(status ? { status } : {}),
			...(allStore ? { all_store: allStore } : {}),
			...(externalCatalogue ? { external_catalogue: externalCatalogue } : {}),
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
