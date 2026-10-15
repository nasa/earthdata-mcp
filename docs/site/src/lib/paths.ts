/**
 * Joins Astro's configured base path with a site-absolute route.
 *
 * Astro normalizes `base` with a trailing slash and routes are written with a
 * leading one, so concatenating them directly doubles the separator.
 */
export function withBase(base: string, path: string): string {
	return `${base.replace(/\/$/, '')}${path}`;
}
