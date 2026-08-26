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

import { TextType, type GraphNodeResponse } from '../services/graph/index';

export interface WorkflowEvidenceSummary {
	plans: string[];
	evidence: string[];
	sql: string[];
	errors: string[];
}

function uniqueText(values: string[]): string[] {
	return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function joinedBlockText(
	block: GraphNodeResponse[],
	predicate: (item: GraphNodeResponse) => boolean,
): string {
	return block
		.filter(predicate)
		.map((item) => item.text)
		.join('')
		.trim();
}

export function summarizeWorkflowEvidence(
	blocks: GraphNodeResponse[][],
): WorkflowEvidenceSummary {
	return {
		plans: uniqueText(
			blocks.map((block) =>
				joinedBlockText(block, (item) =>
					['PlannerNode', 'PlanExecutorNode'].includes(item.nodeName),
				),
			),
		),
		evidence: uniqueText(
			blocks
				.flat()
				.filter((item) => item.nodeName === 'EvidenceRecallNode')
				.flatMap((item) => item.text.split(/\r?\n/))
				.filter((line) => /^证据\d+[：:]/.test(line.trim())),
		),
		sql: uniqueText(
			blocks.map((block) =>
				joinedBlockText(block, (item) => item.textType === TextType.SQL),
			),
		),
		errors: uniqueText(
			blocks
				.flat()
				.filter((item) => item.error)
				.map((item) => item.text),
		),
	};
}
