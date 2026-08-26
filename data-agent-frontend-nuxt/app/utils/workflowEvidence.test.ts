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
import {
	GraphEventType,
	TextType,
	type GraphNodeResponse,
} from '../services/graph/index';
import { summarizeWorkflowEvidence } from './workflowEvidence';

function node(
	nodeName: string,
	text: string,
	textType = TextType.TEXT,
	error = false,
): GraphNodeResponse {
	return {
		agentId: '5',
		threadId: 'm5-test',
		eventType: GraphEventType.NODE_OUTPUT,
		nodeName,
		textType,
		text,
		error,
		complete: false,
	};
}

describe('summarizeWorkflowEvidence', () => {
	it('groups plan, evidence, sql and errors by execution meaning', () => {
		const summary = summarizeWorkflowEvidence([
			[node('PlannerNode', '先汇总销售额')],
			[node('EvidenceRecallNode', '证据1: 销售额仅统计已审核订单\n')],
			[
				node(
					'SqlGenerateNode',
					'SELECT SUM(total_amount) FROM sales_order',
					TextType.SQL,
				),
			],
			[node('SqlExecuteNode', '查询超时', TextType.TEXT, true)],
		]);

		expect(summary.plans).toEqual(['先汇总销售额']);
		expect(summary.evidence).toEqual(['证据1: 销售额仅统计已审核订单']);
		expect(summary.sql).toEqual(['SELECT SUM(total_amount) FROM sales_order']);
		expect(summary.errors).toEqual(['查询超时']);
	});

	it('keeps evidence lines and hides streamed json fragments', () => {
		const summary = summarizeWorkflowEvidence([
			[
				node('EvidenceRecallNode', '{"stand'),
				node('EvidenceRecallNode', 'alone_query":"测试"}'),
				node('EvidenceRecallNode', '证据1: 统一口径\n'),
				node('EvidenceRecallNode', '证据1: 统一口径\n'),
			],
		]);

		expect(summary.evidence).toEqual(['证据1: 统一口径']);
	});

	it('joins streamed plan and sql fragments once per execution step', () => {
		const summary = summarizeWorkflowEvidence([
			[node('PlannerNode', '先查询'), node('PlannerNode', '再汇总')],
			[
				node('SqlGenerateNode', 'SELECT ', TextType.SQL),
				node('SqlGenerateNode', '1', TextType.SQL),
			],
		]);

		expect(summary.plans).toEqual(['先查询再汇总']);
		expect(summary.sql).toEqual(['SELECT 1']);
	});

	it('returns empty groups when no evidence is available', () => {
		expect(summarizeWorkflowEvidence([])).toEqual({
			plans: [],
			evidence: [],
			sql: [],
			errors: [],
		});
	});
});
