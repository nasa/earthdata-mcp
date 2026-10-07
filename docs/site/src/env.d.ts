/*
 * Starlight builds its `virtual:starlight/components/*` modules in a Vite
 * plugin at build time and ships no ambient declarations for them, so
 * TypeScript cannot resolve the imports in src/components/Header.astro. Each
 * virtual module re-exports the component Starlight resolved for that slot,
 * which for the ones below is the stock implementation, so point the types
 * straight at it.
 *
 * Only the components this site overrides the header with are declared. Add to
 * the list if Header.astro starts pulling in more.
 */

declare module 'virtual:starlight/components/Search' {
	export { default } from '@astrojs/starlight/components/Search.astro';
}

declare module 'virtual:starlight/components/SocialIcons' {
	export { default } from '@astrojs/starlight/components/SocialIcons.astro';
}

declare module 'virtual:starlight/components/ThemeSelect' {
	export { default } from '@astrojs/starlight/components/ThemeSelect.astro';
}
