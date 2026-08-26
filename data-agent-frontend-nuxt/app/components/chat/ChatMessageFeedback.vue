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
	<div class="message-feedback" aria-label="回答反馈">
		<span>{{ value ? '已记录反馈' : '这次回答有帮助吗？' }}</span>
		<button
			type="button"
			:class="{ selected: value === 'HELPFUL' }"
			:disabled="loading"
			aria-label="回答有帮助"
			@click="submit('HELPFUL')"
		>
			<v-icon size="15">mdi-thumb-up-outline</v-icon>有帮助
		</button>
		<button
			type="button"
			:class="{ selected: value === 'NOT_HELPFUL' }"
			:disabled="loading"
			aria-label="回答需要改进"
			@click="submit('NOT_HELPFUL')"
		>
			<v-icon size="15">mdi-thumb-down-outline</v-icon>需改进
		</button>
		<span v-if="error" class="feedback-error" role="alert">{{ error }}</span>
	</div>
</template>

<script setup lang="ts">
import { useChatStore } from '~/stores/chat';

const props = defineProps<{
	messageId?: number;
	value?: 'HELPFUL' | 'NOT_HELPFUL';
}>();
const store = useChatStore();
const loading = ref(false);
const error = ref('');

async function submit(value: 'HELPFUL' | 'NOT_HELPFUL') {
	if (loading.value || props.value === value) return;
	loading.value = true;
	error.value = '';
	try {
		await store.submitMessageFeedback(props.messageId, value);
	} catch {
		error.value = '反馈保存失败，请重试。';
	} finally {
		loading.value = false;
	}
}
</script>

<style scoped>
.message-feedback {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 6px;
	margin: 8px 0 0 44px;
	color: #64748b;
	font-size: 11px;
}
button {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	min-height: 34px;
	padding: 5px 9px;
	border: 1px solid #dbe3ef;
	border-radius: 8px;
	background: #fff;
	color: #475569;
	cursor: pointer;
	transition:
		border-color 0.15s ease,
		background 0.15s ease;
}
button:hover:not(:disabled),
button.selected {
	border-color: #93c5fd;
	background: #eff6ff;
	color: #1d4ed8;
}
button:disabled {
	opacity: 0.55;
	cursor: not-allowed;
}
button:focus-visible {
	outline: 3px solid rgba(30, 64, 175, 0.3);
	outline-offset: 2px;
}
.feedback-error {
	color: #b91c1c;
}
@media (max-width: 700px) {
	.message-feedback {
		margin-left: 0;
	}
}
@media (prefers-reduced-motion: reduce) {
	button {
		transition: none;
	}
}
</style>
