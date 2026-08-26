/*
 * Copyright 2026 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { describe, expect, it } from 'vitest';
import { isIncompleteAnalysisRun } from './workflowCompletion';

describe('isIncompleteAnalysisRun', () => {
	it('flags a normal analysis that ends after intermediate nodes', () => {
		expect(
			isIncompleteAnalysisRun({
				nl2sqlOnly: false,
				awaitingHumanFeedback: false,
				hasFinalReply: false,
				hasReport: false,
				hasNodeOutput: true,
			}),
		).toBe(true);
	});

	it.each([
		['report', false, false, false, true, true],
		['final reply', false, false, true, false, true],
		['human review', false, true, false, false, true],
		['nl2sql', true, false, false, false, true],
		['empty run', false, false, false, false, false],
	])(
		'does not flag a valid %s completion',
		(
			_,
			nl2sqlOnly,
			awaitingHumanFeedback,
			hasFinalReply,
			hasReport,
			hasNodeOutput,
		) => {
			expect(
				isIncompleteAnalysisRun({
					nl2sqlOnly,
					awaitingHumanFeedback,
					hasFinalReply,
					hasReport,
					hasNodeOutput,
				}),
			).toBe(false);
		},
	);
});
