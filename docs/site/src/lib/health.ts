/*
 * Turns a health-check outcome into what the status indicator should display.
 *
 * Kept separate from ServerStatus.astro so the mapping can be tested without a
 * DOM or a network. The component keeps the fetch and the element wiring.
 */

export interface HealthReport {
	/** terra-status-indicator variant. */
	variant: string;
	/** Short label shown inside the indicator. */
	label: string;
	/** Supporting sentence shown beside it. */
	detail: string;
}

/**
 * Pass the response, or null when the request never completed. The browser
 * reports network failure, CORS rejection, and timeout identically, so all
 * three collapse into the same null case.
 */
export function describeHealth(response: { ok: boolean; status: number } | null): HealthReport {
	if (!response) {
		return {
			variant: 'unreachable',
			label: 'Unreachable',
			detail: 'Health check did not answer',
		};
	}

	if (response.ok) {
		return {
			variant: 'active',
			label: 'Reachable',
			detail: 'Health check answered successfully',
		};
	}

	return {
		variant: 'testing',
		label: 'Degraded',
		detail: `Health check returned ${response.status}`,
	};
}
