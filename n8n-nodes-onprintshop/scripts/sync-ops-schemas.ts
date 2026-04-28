import * as fs from 'fs';
import * as path from 'path';
import * as https from 'https';
import { IncomingMessage } from 'http';

const DOTENV_PATH = path.join(__dirname, '../.env');
if (fs.existsSync(DOTENV_PATH)) {
	const env = fs.readFileSync(DOTENV_PATH, 'utf8');
	env.split('\n').forEach(line => {
		const [key, value] = line.split('=');
		if (key && value) process.env[key.trim()] = value.trim();
	});
}

const TOKEN = process.env.GITHUB_TOKEN;
const REPO = 'VisualGraphxLLC/ops-automation-knowledge-pack';
const BASE_URL = `https://api.github.com/repos/${REPO}/contents/docs/operations`;

const OPERATIONS = {
	query: [
		'getMasterOptionTag',
		'getOptionGroup',
		'getCustomFormula',
		'getMasterOptionRange',
		'product_additional_options',
	],
	mutation: [
		'setProduct',
		'setProductPrice',
		'setProductSize',
		'setProductPages',
		'setProductCategory',
		'setProductDesign',
		'setAssignOptions',
		'setProductOptionRules',
		'setCustomFormula',
		'setOptionGroup',
		'setMasterOptionTag',
		'setMasterOptionAttributes',
		'setMasterOptionAttributePrice',
	],
};

async function fetchFile(url: string): Promise<string> {
	return new Promise((resolve, reject) => {
		const options = {
			headers: {
				'User-Agent': 'n8n-sync-script',
				'Authorization': TOKEN ? `token ${TOKEN}` : '',
			},
		};

		https.get(url, options, (res: IncomingMessage) => {
			let data = '';
			res.on('data', (chunk: any) => data += chunk);
			res.on('end', () => {
				if (res.statusCode === 200) {
					const json = JSON.parse(data);
					const content = Buffer.from(json.content, 'base64').toString('utf8');
					resolve(content);
				} else {
					reject(new Error(`Failed to fetch ${url}: ${res.statusCode} ${data}`));
				}
			});
		}).on('error', reject);
	});
}

function extractGraphQL(markdown: string): string {
	const match = markdown.match(/```graphql\n([\s\S]*?)\n```/);
	return match ? match[1].trim() : '';
}

async function sync() {
	if (!TOKEN) {
		console.error('GITHUB_TOKEN environment variable is required');
		process.exit(1);
	}

	const queriesPath = path.join(__dirname, '../nodes/OnPrintShop/graphql/queries.ts');
	const mutationsPath = path.join(__dirname, '../nodes/OnPrintShop/graphql/mutations.ts');

	let queriesContent = '';
	let mutationsContent = '';

	for (const op of OPERATIONS.query) {
		console.log(`Syncing query: ${op}...`);
		const content = await fetchFile(`${BASE_URL}/query/${op}.md`);
		const gql = extractGraphQL(content);
		queriesContent += `export const ${op}Query = \`\n${gql}\n\`;\n\n`;
	}

	for (const op of OPERATIONS.mutation) {
		console.log(`Syncing mutation: ${op}...`);
		const content = await fetchFile(`${BASE_URL}/mutation/${op}.md`);
		const gql = extractGraphQL(content);
		mutationsContent += `export const ${op}Mutation = \`\n${gql}\n\`;\n\n`;
	}

	fs.writeFileSync(queriesPath, queriesContent);
	fs.writeFileSync(mutationsPath, mutationsContent);

	console.log('Sync complete!');
}

sync().catch(console.error);
