"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.opsRequest = exports.getAccessToken = void 0;
const n8n_workflow_1 = require("n8n-workflow");
function stripTrailingSlashes(url) {
    return url.replace(/\/+$/, '');
}
function getErrorMessage(error) {
    if (error instanceof Error)
        return error.message;
    return String(error);
}
/**
 * Get OAuth2 access token for OnPrintShop
 */
async function getAccessToken() {
    const credentials = await this.getCredentials('onPrintShopApi');
    const tokenUrl = stripTrailingSlashes(credentials.tokenUrl || 'https://api.onprintshop.com/oauth/token');
    const clientId = credentials.clientId;
    const clientSecret = credentials.clientSecret;
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
        }).catch(async (firstError) => {
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
            }
            catch (secondError) {
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
        const accessToken = tokenResponse === null || tokenResponse === void 0 ? void 0 : tokenResponse.access_token;
        if (!accessToken) {
            throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Failed to get access token: response did not include "access_token"');
        }
        return accessToken;
    }
    catch (error) {
        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `Failed to get access token: ${getErrorMessage(error)}`);
    }
}
exports.getAccessToken = getAccessToken;
/**
 * Make a GraphQL request to OnPrintShop
 */
async function opsRequest(query, variables = {}) {
    const credentials = await this.getCredentials('onPrintShopApi');
    const baseUrl = stripTrailingSlashes(credentials.baseUrl || 'https://api.onprintshop.com');
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
            throw new n8n_workflow_1.NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
        }
        return responseData;
    }
    catch (error) {
        if (error instanceof n8n_workflow_1.NodeOperationError) {
            throw error;
        }
        throw new n8n_workflow_1.NodeOperationError(this.getNode(), `API Request Error: ${getErrorMessage(error)}`);
    }
}
exports.opsRequest = opsRequest;
