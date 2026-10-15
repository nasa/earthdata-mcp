// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	// Horizon's horizon.css ships an invalid `var(transparent)` declaration that
	// lightningcss refuses to parse. esbuild tolerates it. Revert once upstream
	// fixes @nasa-terra/components.
	vite: {
		build: { cssMinify: 'esbuild' },
	},
	site: 'https://nasa.github.io',
	base: '/earthdata-mcp',
	integrations: [
		starlight({
			title: 'Earthdata MCP',
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/nasa/earthdata-mcp' }],
			sidebar: [
				{ label: 'Home', slug: 'index' },
				{ label: 'User guide', slug: 'consumers/earthdata-mcp-server-user-guide' },
				{ label: 'Parameter reference', slug: 'consumers/supported-parameters' },
			],
			components: {
				Head: './src/components/Head.astro',
				Header: './src/components/Header.astro',
			},
			customCss: [
				'@nasa-terra/components/dist/themes/horizon.css',
				'@nasa-terra/components/dist/themes/terra-ui-tokens.css',
				'./src/styles/horizon.css',
				'./src/styles/custom.css',
			]
		}),
	],
});
