// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://nasa.github.io',
	base: '/earthdata-mcp',
	integrations: [
		starlight({
			title: 'Earthdata MCP',
			logo: {
				src: './src/assets/logo.svg'
			},
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/nasa/earthdata-mcp' }],
			sidebar: [
				{ label: 'Home', slug: 'index' },
				{ label: 'User guide', slug: 'consumers/earthdata-mcp-server-user-guide' },
				{ label: 'Parameter reference', slug: 'consumers/supported-parameters' },
			],
			customCss: [
				'./src/styles/custom.css',
			]
		}),
	],
});
