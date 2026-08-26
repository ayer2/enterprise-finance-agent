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
	<section class="welcome-wrap" aria-labelledby="welcome-title">
		<div class="welcome-mark" aria-hidden="true">
			<v-avatar
				v-if="store.currentAgentAvatar"
				:image="store.currentAgentAvatar"
				size="54"
				rounded="lg"
			/>
			<v-icon v-else size="28">mdi-finance</v-icon>
		</div>
		<div class="welcome-copy">
			<div class="welcome-eyebrow">可解释经营分析</div>
			<h2 id="welcome-title">{{ store.currentAgentName || '数据助手' }}</h2>
			<p>
				{{
					store.currentAgentDescription ||
					'提出一个经营问题，我会展示分析计划、口径证据、只读 SQL、查询结果和报告。'
				}}
			</p>
		</div>

		<div class="welcome-divider"><span>推荐问题</span></div>
		<div class="preset-grid" aria-label="推荐问题">
			<button
				v-for="question in questions"
				:key="question"
				type="button"
				class="preset-question"
				:disabled="store.isStreaming"
				@click="ask(question)"
			>
				<span>{{ question }}</span
				><v-icon size="17">mdi-arrow-right</v-icon>
			</button>
		</div>
	</section>
</template>

<script setup lang="ts">
import presetQuestionService from '~/services/presetQuestion/index';
import { useChatStore } from '~/stores/chat';

const store = useChatStore();
const presets = ref<string[]>([]);
const fallbackQuestions = [
	'2025年全年销售额是多少？',
	'2025年12月哪些部门预算执行率超过100%？',
	'逾期60天以上仍未结清的应收有哪些？',
	'华东一部最近三个月销售额是否连续下降？',
];
const questions = computed(() =>
	presets.value.length ? presets.value.slice(0, 4) : fallbackQuestions,
);

watch(
	() => store.currentAgentId,
	async (agentId) => {
		if (!agentId) return;
		try {
			const result = await presetQuestionService.list(agentId);
			presets.value = result
				.filter((item) => item.isActive !== false)
				.map((item) => item.question);
		} catch {
			presets.value = [];
		}
	},
	{ immediate: true },
);

async function ask(question: string) {
	if (!store.currentSession || store.isStreaming) return;
	await store.sendMessage(question);
}
</script>

<style scoped>
.welcome-wrap {
	width: min(840px, 100%);
	margin: auto;
	padding: 40px 28px;
}
.welcome-mark {
	display: grid;
	place-items: center;
	width: 54px;
	height: 54px;
	margin-bottom: 18px;
	border-radius: 14px;
	background: #172554;
	color: #fff;
	box-shadow: 0 10px 24px rgba(23, 37, 84, 0.16);
}
.welcome-copy {
	max-width: 650px;
}
.welcome-eyebrow {
	color: #1d4ed8;
	font-size: 11px;
	font-weight: 800;
	letter-spacing: 0.12em;
	text-transform: uppercase;
}
h2 {
	margin: 5px 0 8px;
	color: #0f172a;
	font-size: 30px;
	letter-spacing: -0.025em;
}
.welcome-copy p {
	margin: 0;
	color: #64748b;
	font-size: 15px;
	line-height: 1.7;
}
.welcome-divider {
	display: flex;
	align-items: center;
	gap: 12px;
	margin: 28px 0 12px;
	color: #64748b;
	font-size: 11px;
	font-weight: 700;
}
.welcome-divider::after {
	content: '';
	height: 1px;
	flex: 1;
	background: #e2e8f0;
}
.preset-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 9px;
}
.preset-question {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	min-height: 64px;
	padding: 12px 14px;
	border: 1px solid #dbe3ef;
	border-radius: 10px;
	background: #fff;
	color: #334155;
	text-align: left;
	font-size: 13px;
	line-height: 1.5;
	cursor: pointer;
	transition:
		border-color 0.18s ease,
		background 0.18s ease;
}
.preset-question:hover:not(:disabled) {
	border-color: #93c5fd;
	background: #f8fbff;
}
.preset-question:focus-visible {
	outline: 3px solid rgba(30, 64, 175, 0.3);
	outline-offset: 2px;
}
.preset-question:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
@media (max-width: 700px) {
	.welcome-wrap {
		padding: 28px 16px;
	}
	.preset-grid {
		grid-template-columns: 1fr;
	}
	h2 {
		font-size: 25px;
	}
}
@media (prefers-reduced-motion: reduce) {
	.preset-question {
		transition: none;
	}
}
</style>
