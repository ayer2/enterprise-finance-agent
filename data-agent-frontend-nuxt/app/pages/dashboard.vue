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
	<main class="finance-dashboard">
		<section class="dashboard-hero" aria-labelledby="dashboard-title">
			<div class="hero-copy">
				<div class="hero-eyebrow">企业经营与财务数据分析</div>
				<h1 id="dashboard-title">先看经营信号，再追到数据依据</h1>
				<p>
					选择一个问题进入分析，Agent 会展示口径证据、执行计划、只读
					SQL、结果和报告。
				</p>
				<div class="hero-actions">
					<v-btn
						color="primary"
						size="large"
						prepend-icon="mdi-message-text-outline"
						:disabled="!agentId"
						@click="openChat()"
						>开始分析</v-btn
					>
					<v-btn
						variant="outlined"
						size="large"
						prepend-icon="mdi-history"
						:disabled="!agentId"
						@click="scrollToHistory"
						>查看最近任务</v-btn
					>
				</div>
			</div>
			<div class="hero-ledger" aria-label="当前分析环境">
				<div class="ledger-heading">
					<span>当前分析环境</span>
					<v-chip
						:color="overallReady ? 'success' : 'warning'"
						size="small"
						variant="tonal"
						>{{ overallReady ? '可以开始' : '需要配置' }}</v-chip
					>
				</div>
				<dl>
					<div>
						<dt>智能体</dt>
						<dd>{{ agent?.name || '未选择' }}</dd>
					</div>
					<div>
						<dt>数据源</dt>
						<dd>{{ datasourceName }}</dd>
					</div>
					<div>
						<dt>业务表</dt>
						<dd>{{ selectedTableCount }} 张</dd>
					</div>
					<div>
						<dt>模型服务</dt>
						<dd>
							{{ modelReady.ready ? 'Chat / Embedding 已就绪' : '未完全就绪' }}
						</dd>
					</div>
				</dl>
			</div>
		</section>

		<section class="status-grid" aria-label="运行状态概览">
			<article
				v-for="item in statusCards"
				:key="item.label"
				class="status-card"
			>
				<div class="status-icon" :class="`status-icon--${item.tone}`">
					<v-icon size="20">{{ item.icon }}</v-icon>
				</div>
				<div>
					<div class="status-label">{{ item.label }}</div>
					<div class="status-value">{{ item.value }}</div>
					<div class="status-note">{{ item.note }}</div>
				</div>
			</article>
		</section>

		<section class="dashboard-section" aria-labelledby="questions-title">
			<div class="section-heading">
				<div>
					<div class="section-eyebrow">推荐分析</div>
					<h2 id="questions-title">从一个经营问题开始</h2>
				</div>
				<span>{{ visibleQuestions.length }} 个可选问题</span>
			</div>
			<div v-if="loading" class="question-grid" aria-label="正在加载推荐问题">
				<v-skeleton-loader
					v-for="index in 4"
					:key="index"
					type="article"
					class="question-skeleton"
				/>
			</div>
			<div v-else class="question-grid">
				<button
					v-for="item in visibleQuestions"
					:key="item.question"
					type="button"
					class="question-card"
					@click="openChat(item.question)"
				>
					<div class="question-meta">
						<span>{{ item.code }}</span
						><v-icon size="18">mdi-arrow-top-right</v-icon>
					</div>
					<h3>{{ item.title }}</h3>
					<p>{{ item.question }}</p>
				</button>
			</div>
		</section>

		<section
			ref="historySection"
			class="dashboard-section"
			aria-labelledby="history-title"
		>
			<div class="section-heading">
				<div>
					<div class="section-eyebrow">分析记录</div>
					<h2 id="history-title">最近任务</h2>
				</div>
				<v-btn
					variant="text"
					color="primary"
					:disabled="!agentId"
					@click="openChat()"
					>打开全部历史</v-btn
				>
			</div>
			<div v-if="sessions.length" class="history-list">
				<button
					v-for="session in sessions.slice(0, 5)"
					:key="session.id"
					type="button"
					class="history-row"
					@click="openSession(session.id)"
				>
					<span class="history-status"
						><v-icon size="16">mdi-check-circle-outline</v-icon></span
					>
					<span class="history-main"
						><strong>{{ session.title || '未命名分析' }}</strong
						><small>{{
							formatTime(session.updateTime || session.createTime)
						}}</small></span
					>
					<v-icon size="18">mdi-chevron-right</v-icon>
				</button>
			</div>
			<div v-else class="empty-history">
				<v-icon size="28">mdi-text-box-search-outline</v-icon>
				<div>
					<strong>还没有分析记录</strong>
					<p>从上方选择一个问题，第一条完整执行轨迹会保存在这里。</p>
				</div>
			</div>
		</section>

		<v-alert
			v-if="loadError"
			type="warning"
			variant="tonal"
			class="mt-4"
			role="alert"
			>{{ loadError }}</v-alert
		>
	</main>
</template>

<script setup lang="ts">
import agentService, { type Agent } from '~/services/agent/index';
import agentDatasourceService from '~/services/agentDatasource/index';
import chatService, { type ChatSession } from '~/services/chat/index';
import modelConfigService, {
	type ModelCheckReady,
} from '~/services/modelConfig/index';
import presetQuestionService, {
	type PresetQuestion,
} from '~/services/presetQuestion/index';

const route = useRoute();
const router = useRouter();
const agentId = computed(() => {
	const value = Number(route.query.agentId);
	return Number.isFinite(value) && value > 0 ? value : undefined;
});
const agent = ref<Agent | null>(null);
const sessions = ref<ChatSession[]>([]);
const presets = ref<PresetQuestion[]>([]);
const activeDatasource = ref<Record<string, unknown> | null>(null);
const modelReady = ref<ModelCheckReady>({
	chatModelReady: false,
	embeddingModelReady: false,
	ready: false,
});
const loading = ref(true);
const loadError = ref('');
const historySection = ref<HTMLElement | null>(null);

const fallbackQuestions = [
	{
		code: 'A01',
		title: '销售趋势',
		question: '华东一部2025年10月至12月销售额是否连续下降？请按月列出。',
	},
	{
		code: 'A02',
		title: '预算预警',
		question: '2025年12月哪些部门和费用类别预算执行率超过100%？',
	},
	{
		code: 'A03',
		title: '应收完整性',
		question: '已审核但尚未生成应收的订单有多少笔？',
	},
	{
		code: 'A04',
		title: '逾期风险',
		question: '截至2025年12月31日，逾期60天以上仍未结清的应收有哪些？',
	},
	{
		code: 'A05',
		title: 'KPI 达成',
		question: '2025年连续两个季度未达标的部门和KPI有哪些？',
	},
	{
		code: 'A06',
		title: '金额核对',
		question: '应收金额与订单金额不一致的记录有哪些？',
	},
];

const visibleQuestions = computed(() => {
	const active = presets.value.filter((item) => item.isActive !== false);
	if (!active.length) return fallbackQuestions;
	return active.slice(0, 6).map((item, index) => ({
		code: `Q${String(index + 1).padStart(2, '0')}`,
		title:
			['经营概览', '趋势分析', '预算监控', '应收风险', '客户洞察', '指标追踪'][
				index
			] || '推荐问题',
		question: item.question,
	}));
});
const selectedTables = computed(() => {
	const value = activeDatasource.value?.selectTables;
	return Array.isArray(value) ? value : [];
});
const selectedTableCount = computed(() => selectedTables.value.length);
const datasourceName = computed(() => {
	const datasource = activeDatasource.value?.datasource;
	return datasource && typeof datasource === 'object' && 'name' in datasource
		? String((datasource as { name?: string }).name || '已连接')
		: '未连接';
});
const overallReady = computed(() =>
	Boolean(agentId.value && modelReady.value.ready && activeDatasource.value),
);
const statusCards = computed(() => [
	{
		label: '模型服务',
		value: modelReady.value.ready ? '已就绪' : '待配置',
		note: 'Chat 与 Embedding',
		icon: 'mdi-cpu-64-bit',
		tone: modelReady.value.ready ? 'good' : 'warn',
	},
	{
		label: '业务数据',
		value: `${selectedTableCount.value} 张表`,
		note: datasourceName.value,
		icon: 'mdi-database-check-outline',
		tone: activeDatasource.value ? 'good' : 'warn',
	},
	{
		label: '历史分析',
		value: `${sessions.value.length} 个会话`,
		note: '可继续下钻追问',
		icon: 'mdi-history',
		tone: 'neutral',
	},
	{
		label: '推荐问题',
		value: `${visibleQuestions.value.length} 个`,
		note: '合成数据场景',
		icon: 'mdi-lightbulb-on-outline',
		tone: 'accent',
	},
]);

async function loadDashboard() {
	loading.value = true;
	loadError.value = '';
	if (!agentId.value) {
		loading.value = false;
		loadError.value = '请先从左侧选择一个智能体。';
		return;
	}
	const results = await Promise.allSettled([
		agentService.get(agentId.value),
		chatService.getAgentSessions(agentId.value),
		presetQuestionService.list(agentId.value),
		agentDatasourceService.getActiveAgentDatasource(agentId.value),
		modelConfigService.checkReady(),
	]);
	if (results[0].status === 'fulfilled') agent.value = results[0].value;
	if (results[1].status === 'fulfilled') sessions.value = results[1].value;
	if (results[2].status === 'fulfilled') presets.value = results[2].value;
	if (results[3].status === 'fulfilled')
		activeDatasource.value = results[3].value as unknown as Record<
			string,
			unknown
		>;
	if (results[4].status === 'fulfilled') modelReady.value = results[4].value;
	const failed = results.filter(
		(result) => result.status === 'rejected',
	).length;
	if (failed)
		loadError.value = `${failed} 项运行状态暂时无法读取，其余内容仍可使用。`;
	loading.value = false;
}
function openChat(question?: string) {
	if (!agentId.value) return;
	const query: Record<string, string> = { agentId: String(agentId.value) };
	if (question) query.question = question;
	router.push({ path: '/chat', query });
}
function openSession(sessionId: string) {
	if (!agentId.value) return;
	router.push({
		path: '/chat',
		query: { agentId: String(agentId.value), sessionId },
	});
}
function scrollToHistory() {
	historySection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function formatTime(value?: Date) {
	if (!value) return '时间未知';
	const date = new Date(value);
	return Number.isNaN(date.getTime())
		? '时间未知'
		: date.toLocaleString('zh-CN', {
				month: '2-digit',
				day: '2-digit',
				hour: '2-digit',
				minute: '2-digit',
			});
}
watch(agentId, loadDashboard, { immediate: true });
</script>

<style scoped>
.finance-dashboard {
	--ink: #172554;
	--muted: #64748b;
	--line: #dbe3ef;
	min-height: 100%;
	padding: 28px;
	background: #f8fafc;
	color: var(--ink);
}
.dashboard-hero {
	display: grid;
	grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.75fr);
	gap: 24px;
	padding: 32px;
	border: 1px solid #dbeafe;
	border-radius: 18px;
	background: linear-gradient(120deg, #fff 0 65%, #eff6ff 65% 100%);
}
.hero-eyebrow,
.section-eyebrow {
	color: #1d4ed8;
	font-size: 11px;
	font-weight: 800;
	letter-spacing: 0.12em;
	text-transform: uppercase;
}
h1 {
	max-width: 720px;
	margin: 8px 0 12px;
	font-size: clamp(30px, 4vw, 48px);
	line-height: 1.08;
	letter-spacing: -0.035em;
}
.hero-copy > p {
	max-width: 680px;
	margin: 0;
	color: var(--muted);
	font-size: 16px;
	line-height: 1.75;
}
.hero-actions {
	display: flex;
	flex-wrap: wrap;
	gap: 12px;
	margin-top: 24px;
}
.hero-ledger {
	align-self: stretch;
	padding: 18px;
	border-radius: 14px;
	background: #0f172a;
	color: #f8fafc;
	box-shadow: 0 16px 36px rgba(15, 23, 42, 0.12);
}
.ledger-heading {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	margin-bottom: 14px;
	font-weight: 700;
}
.hero-ledger dl {
	margin: 0;
}
.hero-ledger dl div {
	display: grid;
	grid-template-columns: 84px 1fr;
	gap: 12px;
	padding: 10px 0;
	border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.hero-ledger dt {
	color: #94a3b8;
	font-size: 12px;
}
.hero-ledger dd {
	margin: 0;
	text-align: right;
	font:
		500 12px/1.5 ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}
.status-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 12px;
	margin: 16px 0 28px;
}
.status-card {
	display: flex;
	align-items: flex-start;
	gap: 12px;
	min-width: 0;
	padding: 16px;
	border: 1px solid var(--line);
	border-radius: 12px;
	background: #fff;
}
.status-icon {
	display: grid;
	place-items: center;
	width: 40px;
	height: 40px;
	flex: 0 0 40px;
	border-radius: 10px;
	background: #e9eef6;
	color: #334155;
}
.status-icon--good {
	background: #dcfce7;
	color: #166534;
}
.status-icon--warn {
	background: #fef3c7;
	color: #92400e;
}
.status-icon--accent {
	background: #ffedd5;
	color: #9a3412;
}
.status-label {
	color: var(--muted);
	font-size: 11px;
}
.status-value {
	margin: 2px 0;
	font-size: 19px;
	font-weight: 800;
	font-variant-numeric: tabular-nums;
}
.status-note {
	overflow: hidden;
	color: #94a3b8;
	font-size: 11px;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.dashboard-section {
	scroll-margin-top: 80px;
	margin-top: 24px;
}
.section-heading {
	display: flex;
	align-items: flex-end;
	justify-content: space-between;
	gap: 16px;
	margin-bottom: 14px;
}
.section-heading h2 {
	margin: 3px 0 0;
	font-size: 24px;
}
.section-heading > span {
	color: var(--muted);
	font-size: 12px;
}
.question-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 12px;
}
.question-card {
	min-height: 172px;
	padding: 18px;
	border: 1px solid var(--line);
	border-radius: 13px;
	background: #fff;
	text-align: left;
	color: inherit;
	cursor: pointer;
	transition:
		border-color 0.18s ease,
		box-shadow 0.18s ease,
		transform 0.18s ease;
}
.question-card:hover {
	border-color: #93c5fd;
	box-shadow: 0 10px 28px rgba(30, 64, 175, 0.09);
	transform: translateY(-2px);
}
.question-card:focus-visible,
.history-row:focus-visible {
	outline: 3px solid rgba(30, 64, 175, 0.3);
	outline-offset: 2px;
}
.question-card h3 {
	margin: 18px 0 8px;
	font-size: 17px;
}
.question-card p {
	margin: 0;
	color: var(--muted);
	font-size: 13px;
	line-height: 1.65;
}
.question-meta {
	display: flex;
	align-items: center;
	justify-content: space-between;
	color: #1d4ed8;
	font:
		700 11px ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}
.question-skeleton {
	border: 1px solid var(--line);
	border-radius: 13px;
}
.history-list {
	overflow: hidden;
	border: 1px solid var(--line);
	border-radius: 13px;
	background: #fff;
}
.history-row {
	display: grid;
	grid-template-columns: 32px 1fr 24px;
	align-items: center;
	gap: 10px;
	width: 100%;
	min-height: 64px;
	padding: 10px 16px;
	border: 0;
	border-bottom: 1px solid #eef2f7;
	background: #fff;
	color: inherit;
	text-align: left;
	cursor: pointer;
}
.history-row:last-child {
	border-bottom: 0;
}
.history-row:hover {
	background: #f8fbff;
}
.history-status {
	color: #16a34a;
}
.history-main {
	display: flex;
	min-width: 0;
	flex-direction: column;
	gap: 3px;
}
.history-main strong {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	font-size: 13px;
}
.history-main small {
	color: var(--muted);
	font-size: 11px;
}
.empty-history {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 24px;
	border: 1px dashed #cbd5e1;
	border-radius: 13px;
	background: #fff;
	color: var(--muted);
}
.empty-history strong {
	color: var(--ink);
}
.empty-history p {
	margin: 4px 0 0;
	font-size: 13px;
}
@media (max-width: 1100px) {
	.dashboard-hero {
		grid-template-columns: 1fr;
	}
	.status-grid {
		grid-template-columns: repeat(2, 1fr);
	}
	.question-grid {
		grid-template-columns: repeat(2, 1fr);
	}
}
@media (max-width: 700px) {
	.finance-dashboard {
		padding: 16px;
	}
	.dashboard-hero {
		padding: 22px;
		background: #fff;
	}
	.status-grid,
	.question-grid {
		grid-template-columns: 1fr;
	}
	.hero-actions .v-btn {
		width: 100%;
	}
	.section-heading {
		align-items: flex-start;
		flex-direction: column;
	}
	.question-card {
		min-height: 0;
	}
}
@media (prefers-reduced-motion: reduce) {
	.question-card {
		transition: none;
	}
	.question-card:hover {
		transform: none;
	}
}
</style>
