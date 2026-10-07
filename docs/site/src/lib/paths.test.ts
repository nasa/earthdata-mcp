import { describe, expect, it } from 'vitest';

import { withBase } from './paths';

describe('withBase', () => {
	// What Astro actually hands us for this site: base is '/earthdata-mcp/'.
	it('does not double the slash when base has a trailing one', () => {
		expect(withBase('/earthdata-mcp/', '/consumers/supported-parameters/')).toBe(
			'/earthdata-mcp/consumers/supported-parameters/'
		);
	});

	it('handles a base without a trailing slash', () => {
		expect(withBase('/earthdata-mcp', '/consumers/supported-parameters/')).toBe(
			'/earthdata-mcp/consumers/supported-parameters/'
		);
	});

	// The default when no base is configured, as in a local root deployment.
	it('leaves the path alone when base is the site root', () => {
		expect(withBase('/', '/')).toBe('/');
		expect(withBase('/', '/consumers/')).toBe('/consumers/');
	});
});
