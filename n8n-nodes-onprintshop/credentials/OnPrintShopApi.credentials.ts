import {
	ICredentialType,
	INodeProperties,
	Icon,
} from 'n8n-workflow';

export class OnPrintShopApi implements ICredentialType {
	name = 'onPrintShopApi';
	displayName = 'OnPrintShop API';
	icon: Icon = 'file:onprintshop.svg';
	documentationUrl = 'https://documenter.getpostman.com/view/33263100/2sA3kVmMgH#intro';
	properties: INodeProperties[] = [
		{
			displayName: 'Client ID',
			name: 'clientId',
			type: 'string',
			default: '',
			required: true,
			description: 'OAuth2 Client ID from OnPrintShop',
		},
		{
			displayName: 'Client Secret',
			name: 'clientSecret',
			type: 'string',
			typeOptions: {
				password: true,
			},
			default: '',
			required: true,
			description: 'OAuth2 Client Secret from OnPrintShop',
		},
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'https://api.onprintshop.com',
			required: true,
			description: 'The base URL for your OnPrintShop instance',
		},
		{
			displayName: 'Token URL',
			name: 'tokenUrl',
			type: 'string',
			default: 'https://api.onprintshop.com/oauth/token',
			required: true,
			description: 'The OAuth2 token endpoint URL',
		},
	];
}

