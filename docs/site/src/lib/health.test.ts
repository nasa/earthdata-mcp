import { describe, expect, it } from 'vitest';

import { describeHealth } from './health';

describe('describeHealth', () => {
	it('reports a 2xx response as reachable', () => {
		expect(describeHealth({ ok: true, status: 200 })).toEqual({
			variant: 'active',
			label: 'Reachable',
			detail: 'Health check answered successfully',
		});
	});

	it('reports a non-ok response as degraded and names the status', () => {
		const report = describeHealth({ ok: false, status: 503 });

		expect(report.variant).toBe('testing');
		expect(report.label).toBe('Degraded');
		expect(report.detail).toContain('503');
	});

	it('reports a failed request as unreachable', () => {
		expect(describeHealth(null)).toEqual({
			variant: 'unreachable',
			label: 'Unreachable',
			detail: 'Health check did not answer',
		});
	});

	// The red dot is styled off this exact attribute value in horizon.css, via
	// terra-status-indicator[variant='unreachable']::part(dot). Renaming it here
	// silently drops the failure colour, so pin it.
	it('uses the variant the stylesheet hooks onto for failures', () => {
		expect(describeHealth(null).variant).toBe('unreachable');
	});
});
