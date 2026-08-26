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

export interface MessageFeedbackMetadata {
	targetMessageId: number;
	value: 'HELPFUL' | 'NOT_HELPFUL';
}

export function parseMessageFeedbackMetadata(
	metadata?: string,
): MessageFeedbackMetadata | undefined {
	if (!metadata) return undefined;
	try {
		let parsed: unknown = JSON.parse(metadata);
		if (typeof parsed === 'string') parsed = JSON.parse(parsed);
		if (!parsed || typeof parsed !== 'object') return undefined;
		const candidate = parsed as Partial<MessageFeedbackMetadata>;
		if (
			typeof candidate.targetMessageId !== 'number' ||
			!['HELPFUL', 'NOT_HELPFUL'].includes(candidate.value || '')
		)
			return undefined;
		return candidate as MessageFeedbackMetadata;
	} catch {
		return undefined;
	}
}
