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
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mybatis.spring.boot.test.autoconfigure.MybatisTest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.assertj.core.api.Assertions.assertThat;

@MybatisTest
class SqlAuditLogMapperIntegrationTest {

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Autowired
	private SqlAuditLogMapper mapper;

	@BeforeEach
	void setUp() {
		jdbcTemplate.execute("DROP TABLE IF EXISTS sql_audit_log");
		jdbcTemplate.execute("""
				CREATE TABLE sql_audit_log (
				  id BIGINT AUTO_INCREMENT PRIMARY KEY,
				  agent_id BIGINT NOT NULL,
				  thread_id VARCHAR(255),
				  actor_id VARCHAR(255),
				  data_role VARCHAR(50),
				  question CLOB,
				  sql_text CLOB,
				  duration_ms BIGINT NOT NULL,
				  result_count INT,
				  status VARCHAR(32) NOT NULL,
				  failure_reason VARCHAR(1000),
				  created_time TIMESTAMP NOT NULL
				)
				""");
	}

	@Test
	void insertPersistsExecutionEvidenceAndGeneratedId() {
		SqlAuditLog auditLog = SqlAuditLog.builder()
			.agentId(5L)
			.threadId("m4-normal-query")
			.actorId("m4-verifier")
			.dataRole("ANALYST")
			.question("2025年全年销售额是多少？")
			.sqlText("SELECT SUM(total_amount) FROM sales_order")
			.durationMs(125L)
			.resultCount(1)
			.status("SUCCESS")
			.build();

		assertThat(mapper.insert(auditLog)).isEqualTo(1);
		assertThat(auditLog.getId()).isPositive();

		Map<String, Object> row = jdbcTemplate.queryForMap("SELECT * FROM sql_audit_log WHERE id = ?",
				auditLog.getId());
		assertThat(row).containsEntry("agent_id", 5L)
			.containsEntry("thread_id", "m4-normal-query")
			.containsEntry("actor_id", "m4-verifier")
			.containsEntry("data_role", "ANALYST")
			.containsEntry("duration_ms", 125L)
			.containsEntry("result_count", 1)
			.containsEntry("status", "SUCCESS");
		assertThat(row.get("question").toString()).contains("全年销售额");
		assertThat(row.get("sql_text").toString()).contains("sales_order");
		assertThat(row.get("created_time")).isNotNull();
	}

}
