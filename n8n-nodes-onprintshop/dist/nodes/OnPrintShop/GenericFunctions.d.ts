import { IExecuteFunctions, IDataObject } from 'n8n-workflow';
/**
 * Get OAuth2 access token for OnPrintShop
 */
export declare function getAccessToken(this: IExecuteFunctions): Promise<string>;
/**
 * Make a GraphQL request to OnPrintShop
 */
export declare function opsRequest(this: IExecuteFunctions, query: string, variables?: IDataObject): Promise<any>;
