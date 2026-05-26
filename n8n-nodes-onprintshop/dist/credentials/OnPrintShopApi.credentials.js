"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OnPrintShopApi = void 0;
class OnPrintShopApi {
    constructor() {
        this.name = 'onPrintShopApi';
        this.displayName = 'OnPrintShop API';
        this.icon = 'file:onprintshop.svg';
        this.documentationUrl = 'https://documenter.getpostman.com/view/33263100/2sA3kVmMgH#intro';
        this.properties = [
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
}
exports.OnPrintShopApi = OnPrintShopApi;
