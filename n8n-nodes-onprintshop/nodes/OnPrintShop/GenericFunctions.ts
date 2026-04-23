import {
	IExecuteFunctions,
	IDataObject,
	NodeOperationError,
} from 'n8n-workflow';

/**
 * Get OAuth2 access token for OnPrintShop
 */
export async function getAccessToken(this: IExecuteFunctions): Promise<string> {
	const credentials = await this.getCredentials('onPrintShopApi');
	const tokenUrl = credentials.tokenUrl as string || 'https://api.onprintshop.com/oauth/token';
	const clientId = credentials.clientId as string;
	const clientSecret = credentials.clientSecret as string;

	try {
		const tokenResponse = await this.helpers.request({
			method: 'POST',
			url: tokenUrl,
			headers: {
				'Content-Type': 'application/json',
			},
			body: {
				grant_type: 'client_credentials',
				client_id: clientId,
				client_secret: clientSecret,
			},
			json: true,
		});
		return tokenResponse.access_token;
	} catch (error) {
		throw new NodeOperationError(this.getNode(), `Failed to get access token: ${error.message}`);
	}
}

/**
 * Make a GraphQL request to OnPrintShop
 */
export async function opsRequest(
	this: IExecuteFunctions,
	query: string,
	variables: IDataObject = {},
): Promise<any> {
	const credentials = await this.getCredentials('onPrintShopApi');
	const baseUrl = credentials.baseUrl as string || 'https://api.onprintshop.com';
	const accessToken = await getAccessToken.call(this);

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

		if (responseData.errors) {
			throw new NodeOperationError(
				this.getNode(),
				`GraphQL Error: ${JSON.stringify(responseData.errors)}`,
			);
		}

		return responseData;
	} catch (error) {
		if (error instanceof NodeOperationError) {
			throw error;
		}
		throw new NodeOperationError(this.getNode(), `API Request Error: ${error.message}`);
	}
}
