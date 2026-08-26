<!--
  Copyright 2026 the original author or authors.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

       https://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
-->

<template>
	<section v-if="hasContent" class="execution-brief" aria-label="执行依据摘要">
		<div class="brief-rail" aria-hidden="true" />
		<div class="brief-heading">
			<div>
				<div class="brief-eyebrow">执行依据</div>
				<h3>这次分析为什么可信</h3>
			</div>
			<div class="brief-counts" aria-label="依据数量">
				<span>{{ summary.plans.length }} 项计划</span>
				<span>{{ summary.evidence.length }} 条证据</span>
				<span>{{ summary.sql.length }} 段 SQL</span>
			</div>
		</div>

		<div class="brief-grid">
			<details v-if="summary.plans.length" class="brief-panel" open>
				<summary>
					<v-icon size="16">mdi-clipboard-text-outline</v-icon>分析计划
				</summary>
				<div class="panel-content">
					<p v-for="(item, index) in summary.plans" :key="`plan-${index}`">
						{{ item }}
					</p>
				</div>
			</details>

			<details v-if="summary.evidence.length" class="brief-panel" open>
				<summary>
					<v-icon size="16">mdi-file-check-outline</v-icon>口径与证据
				</summary>
				<div class="panel-content">
					<p
						v-for="(item, index) in summary.evidence"
						:key="`evidence-${index}`"
					>
						{{ item }}
					</p>
				</div>
			</details>

			<details v-if="summary.sql.length" class="brief-panel brief-panel--sql">
				<summary><v-icon size="16">mdi-code-braces</v-icon>生成 SQL</summary>
				<div class="panel-content">
					<div
						v-for="(item, index) in summary.sql"
						:key="`sql-${index}`"
						class="sql-wrap"
					>
						<button
							type="button"
							class="copy-button"
							:aria-label="`复制第 ${index + 1} 段 SQL`"
							@click="copySql(item)"
						>
							<v-icon size="14">{{
								copiedSql === item ? 'mdi-check' : 'mdi-content-copy'
							}}</v-icon>
							{{ copiedSql === item ? '已复制' : '复制' }}
						</button>
						<pre><code>{{ item }}</code></pre>
					</div>
				</div>
			</details>
		</div>

		<div v-if="summary.errors.length" class="brief-error" role="alert">
			<v-icon size="16">mdi-alert-circle-outline</v-icon>
			<span>{{ summary.errors.join('；') }}</span>
		</div>
	</section>
</template>

<script setup lang="ts">
import type { GraphNodeResponse } from '~/services/graph/index';
import { summarizeWorkflowEvidence } from '~/utils/workflowEvidence';

const props = defineProps<{ nodeBlocks: GraphNodeResponse[][] }>();
const summary = computed(() => summarizeWorkflowEvidence(props.nodeBlocks));
const hasContent = computed(() =>
	Object.values(summary.value).some((items) => items.length > 0),
);
const copiedSql = ref('');

async function copySql(sql: string) {
	try {
		await navigator.clipboard.writeText(sql);
	} catch {
		return;
	}
	copiedSql.value = sql;
	setTimeout(() => {
		if (copiedSql.value === sql) copiedSql.value = '';
	}, 1800);
}
</script>

<style scoped>
.execution-brief {
	position: relative;
	margin-bottom: 18px;
	padding: 16px 16px 16px 20px;
	border: 1px solid #dbeafe;
	border-radius: 12px;
	background: #f8fbff;
	overflow: hidden;
}
.brief-rail {
	position: absolute;
	inset: 0 auto 0 0;
	width: 4px;
	background: linear-gradient(180deg, #1e40af 0 68%, #d97706 68% 100%);
}
.brief-heading {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 16px;
	margin-bottom: 12px;
}
.brief-eyebrow {
	font-size: 10px;
	font-weight: 700;
	letter-spacing: 0.12em;
	color: #1d4ed8;
	text-transform: uppercase;
}
h3 {
	margin: 2px 0 0;
	font-size: 15px;
	color: #172554;
}
.brief-counts {
	display: flex;
	flex-wrap: wrap;
	justify-content: flex-end;
	gap: 6px;
}
.brief-counts span {
	padding: 3px 8px;
	border-radius: 999px;
	background: #e9eef6;
	font-size: 10.5px;
	color: #334155;
}
.brief-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 8px;
}
.brief-panel {
	min-width: 0;
	border: 1px solid #dbe3ef;
	border-radius: 9px;
	background: #fff;
}
.brief-panel--sql {
	grid-column: 1 / -1;
}
summary {
	display: flex;
	align-items: center;
	gap: 6px;
	min-height: 44px;
	padding: 9px 11px;
	cursor: pointer;
	font-size: 12px;
	font-weight: 700;
	color: #1e3a8a;
	list-style: none;
}
summary::-webkit-details-marker {
	display: none;
}
summary:focus-visible,
.copy-button:focus-visible {
	outline: 3px solid rgba(30, 64, 175, 0.3);
	outline-offset: 2px;
}
.panel-content {
	padding: 0 11px 11px;
	font-size: 12px;
	line-height: 1.65;
	color: #475569;
}
.panel-content p {
	margin: 0 0 6px;
	white-space: pre-wrap;
	word-break: break-word;
}
.sql-wrap {
	position: relative;
}
pre {
	margin: 0;
	padding: 12px;
	border-radius: 8px;
	background: #0f172a;
	color: #e2e8f0;
	overflow-x: auto;
	font:
		12px/1.6 ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}
.copy-button {
	position: absolute;
	top: 6px;
	right: 6px;
	display: inline-flex;
	align-items: center;
	gap: 4px;
	min-height: 32px;
	padding: 4px 8px;
	border: 1px solid #475569;
	border-radius: 6px;
	background: #1e293b;
	color: #f8fafc;
	font-size: 11px;
	cursor: pointer;
}
.brief-error {
	display: flex;
	align-items: flex-start;
	gap: 7px;
	margin-top: 10px;
	padding: 9px 10px;
	border-radius: 8px;
	background: #fef2f2;
	color: #b91c1c;
	font-size: 12px;
}
@media (max-width: 700px) {
	.brief-heading {
		flex-direction: column;
	}
	.brief-counts {
		justify-content: flex-start;
	}
	.brief-grid {
		grid-template-columns: 1fr;
	}
	.brief-panel--sql {
		grid-column: auto;
	}
}
@media (prefers-reduced-motion: reduce) {
	* {
		scroll-behavior: auto !important;
		transition: none !important;
	}
}
</style>
