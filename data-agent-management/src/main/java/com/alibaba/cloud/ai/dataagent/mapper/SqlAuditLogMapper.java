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
package com.alibaba.cloud.ai.dataagent.mapper;

import com.alibaba.cloud.ai.dataagent.entity.SqlAuditLog;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;

@Mapper
public interface SqlAuditLogMapper {

	@Insert("""
			INSERT INTO sql_audit_log
			(agent_id, thread_id, actor_id, data_role, question, sql_text, duration_ms, result_count, status,
			 failure_reason, created_time)
			VALUES
			(#{agentId}, #{threadId}, #{actorId}, #{dataRole}, #{question}, #{sqlText}, #{durationMs}, #{resultCount},
			 #{status}, #{failureReason}, CURRENT_TIMESTAMP)
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
	int insert(SqlAuditLog auditLog);

}
