import {
	IExecuteFunctions,
	IDataObject,
	NodeOperationError,
} from 'n8n-workflow';

function stripTrailingSlashes(url: string): string {
	return url.replace(/\/+$/, '');
}

function getErrorMessage(error: unknown): string {
	if (error instanceof Error) return error.message;
	return String(error);
}

/**
 * Get OAuth2 access token for OnPrintShop
 */
export async function getAccessToken(this: IExecuteFunctions): Promise<string> {
	const credentials = await this.getCredentials('onPrintShopApi');
	const tokenUrl = stripTrailingSlashes((credentials.tokenUrl as string) || 'https://api.onprintshop.com/oauth/token');
	const clientId = credentials.clientId as string;
	const clientSecret = credentials.clientSecret as string;

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
			}).catch(async (firstError: unknown) => {
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
				} catch (secondError: unknown) {
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

		const accessToken = tokenResponse?.access_token;
		if (!accessToken) {
			throw new NodeOperationError(
				this.getNode(),
				'Failed to get access token: response did not include "access_token"',
			);
		}

		return accessToken;
	} catch (error) {
		throw new NodeOperationError(this.getNode(), `Failed to get access token: ${getErrorMessage(error)}`);
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
	const baseUrl = stripTrailingSlashes((credentials.baseUrl as string) || 'https://api.onprintshop.com');
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
		throw new NodeOperationError(this.getNode(), `API Request Error: ${getErrorMessage(error)}`);
	}
}
