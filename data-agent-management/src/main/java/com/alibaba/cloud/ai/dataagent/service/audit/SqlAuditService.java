/*
 * Copyright 2024-2026 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.alibaba.cloud.ai.dataagent.service.audit;

import com.alibaba.cloud.ai.dataagent.entity.SqlAuditLog;
import com.alibaba.cloud.ai.dataagent.mapper.SqlAuditLogMapper;
import com.alibaba.cloud.ai.dataagent.security.sql.QuerySecurityContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/** Writes SQL audit records without exposing database credentials. */
@Slf4j
@Service
@RequiredArgsConstructor
public class SqlAuditService {

	private final SqlAuditLogMapper mapper;

	public void record(long agentId, String threadId, QuerySecurityContext context, String question, String sql,
			long durationMs, Integer resultCount, String status, String failureReason) {
		try {
			mapper.insert(SqlAuditLog.builder()
				.agentId(agentId)
				.threadId(threadId)
				.actorId(context.actorId())
				.dataRole(context.role())
				.question(question)
				.sqlText(sql)
				.durationMs(durationMs)
				.resultCount(resultCount)
				.status(status)
				.failureReason(abbreviate(failureReason, 1000))
				.build());
		}
		catch (RuntimeException ex) {
			log.error("Failed to persist SQL audit record for agent {} and thread {}", agentId, threadId, ex);
		}
	}

	private static String abbreviate(String value, int maxLength) {
		if (value == null || value.length() <= maxLength) {
			return value;
		}
		return value.substring(0, maxLength);
	}

}
