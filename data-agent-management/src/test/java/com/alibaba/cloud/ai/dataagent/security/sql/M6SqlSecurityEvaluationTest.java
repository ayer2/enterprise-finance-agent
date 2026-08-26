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
package com.alibaba.cloud.ai.dataagent.security.sql;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.alibaba.cloud.ai.dataagent.mapper.AgentDatasourceTablesMapper;
import com.alibaba.cloud.ai.dataagent.properties.DataAgentProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

/** Produces the machine-readable M6 SQL security evaluation evidence. */
class M6SqlSecurityEvaluationTest {

	private static final long AGENT_ID = 5L;

	private final ObjectMapper objectMapper = new ObjectMapper();

	@Test
	void evaluateAllVersionedSecurityCases() throws IOException {
		Path casesPath = locateCases();
		JsonNode cases = objectMapper.readTree(casesPath.toFile());
		SqlSecurityService service = createService();
		List<Map<String, Object>> attackResults = new ArrayList<>();
		List<Map<String, Object>> allowedResults = new ArrayList<>();

		for (JsonNode attack : cases.path("attacks")) {
			attackResults.add(evaluateAttack(service, attack));
		}
		for (JsonNode allowed : cases.path("allowed")) {
			allowedResults.add(evaluateAllowed(service, allowed));
		}

		long blocked = attackResults.stream().filter(result -> Boolean.TRUE.equals(result.get("passed"))).count();
		long allowed = allowedResults.stream().filter(result -> Boolean.TRUE.equals(result.get("passed"))).count();
		BigDecimal blockRate = BigDecimal.valueOf(blocked)
			.divide(BigDecimal.valueOf(attackResults.size()), 6, RoundingMode.HALF_UP);
		Map<String, Object> evidence = new LinkedHashMap<>();
		evidence.put("attackTotal", attackResults.size());
		evidence.put("attackBlocked", blocked);
		evidence.put("dangerousRequestBlockRate", blockRate);
		evidence.put("allowedTotal", allowedResults.size());
		evidence.put("allowedPassed", allowed);
		evidence.put("attacks", attackResults);
		evidence.put("allowed", allowedResults);
		Path output = outputPath();
		Files.createDirectories(output.getParent());
		objectMapper.writerWithDefaultPrettyPrinter().writeValue(output.toFile(), evidence);

		assertTrue(attackResults.stream().allMatch(result -> Boolean.TRUE.equals(result.get("passed"))),
				() -> "at least one dangerous SQL case was not blocked as expected: " + attackResults);
		assertTrue(allowedResults.stream().allMatch(result -> Boolean.TRUE.equals(result.get("passed"))),
				() -> "at least one normal SQL case was rejected: " + allowedResults);
	}

	private Map<String, Object> evaluateAttack(SqlSecurityService service, JsonNode attack) {
		String id = attack.path("id").asText();
		String expectedCode = attack.path("expectedCode").asText();
		String actualCode = null;
		String errorType = null;
		try {
			service.validateAndPrepare(AGENT_ID, attack.path("sql").asText(), "mysql", context(attack));
		}
		catch (SqlSecurityException ex) {
			actualCode = code(ex.getMessage());
			errorType = ex.getClass().getSimpleName();
		}
		Map<String, Object> result = new LinkedHashMap<>();
		result.put("id", id);
		result.put("expectedCode", expectedCode);
		result.put("actualCode", actualCode);
		result.put("errorType", errorType);
		result.put("passed", expectedCode.equals(actualCode));
		return result;
	}

	private Map<String, Object> evaluateAllowed(SqlSecurityService service, JsonNode allowed) {
		Map<String, Object> result = new LinkedHashMap<>();
		result.put("id", allowed.path("id").asText());
		try {
			SqlSecurityDecision decision = service.validateAndPrepare(AGENT_ID, allowed.path("sql").asText(), "mysql",
					context(allowed));
			boolean scopeMatches = !allowed.path("expectDepartmentScope").asBoolean(false)
					|| decision.departmentScopeApplied();
			result.put("departmentScopeApplied", decision.departmentScopeApplied());
			result.put("passed", scopeMatches);
		}
		catch (SqlSecurityException ex) {
			result.put("actualCode", code(ex.getMessage()));
			result.put("passed", false);
		}
		return result;
	}

	private QuerySecurityContext context(JsonNode item) {
		List<Long> departmentIds = new ArrayList<>();
		item.path("departmentIds").forEach(value -> departmentIds.add(value.asLong()));
		String role = item.path("role").asText("ANALYST");
		return new QuerySecurityContext("m6-evaluator", role, departmentIds, false);
	}

	private SqlSecurityService createService() {
		AgentDatasourceTablesMapper mapper = mock(AgentDatasourceTablesMapper.class);
		when(mapper.getSelectedTablesByAgentId(AGENT_ID))
			.thenReturn(List.of("org_department", "employee", "customer", "contract", "sales_order",
					"sales_order_item", "receivable", "payment", "budget", "expense", "kpi_definition",
					"kpi_target", "kpi_value"));
		DataAgentProperties properties = new DataAgentProperties();
		properties.getSqlSecurity()
			.setAllowedColumns(Map.of("org_department", Set.of("id", "name", "region", "parent_id"), "employee",
					Set.of("id", "department_id", "name", "email"), "customer",
					Set.of("id", "name", "industry", "region", "credit_level"), "sales_order",
					Set.of("id", "department_id", "customer_id", "order_date", "total_amount", "status")));
		return new SqlSecurityService(mapper, properties);
	}

	private String code(String message) {
		if (message == null || message.isBlank()) {
			return null;
		}
		int separator = message.indexOf(':');
		return separator < 0 ? message : message.substring(0, separator);
	}

	private Path locateCases() {
		Path workingDirectory = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
		List<Path> candidates = List.of(
				workingDirectory.resolve("demo/enterprise-finance/m4/security-cases.json"),
				workingDirectory.resolve("../demo/enterprise-finance/m4/security-cases.json").normalize());
		return candidates.stream()
			.filter(Files::isRegularFile)
			.findFirst()
			.orElseThrow(() -> new IllegalStateException("cannot locate M4 security cases from " + workingDirectory));
	}

	private Path outputPath() {
		Path workingDirectory = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
		if (workingDirectory.getFileName().toString().equals("data-agent-management")) {
			return workingDirectory.resolve("target/m6-security-evaluation.json");
		}
		return workingDirectory.resolve("data-agent-management/target/m6-security-evaluation.json");
	}

}
