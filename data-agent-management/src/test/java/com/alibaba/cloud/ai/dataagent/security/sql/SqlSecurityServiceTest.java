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

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.lenient;

import com.alibaba.cloud.ai.dataagent.bo.schema.ResultSetBO;
import com.alibaba.cloud.ai.dataagent.mapper.AgentDatasourceTablesMapper;
import com.alibaba.cloud.ai.dataagent.properties.DataAgentProperties;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class SqlSecurityServiceTest {

	@Mock
	private AgentDatasourceTablesMapper tablesMapper;

	private DataAgentProperties properties;

	private SqlSecurityService service;

	@BeforeEach
	void setUp() {
		properties = new DataAgentProperties();
		properties.getSqlSecurity()
			.setAllowedColumns(Map.of("sales_order",
					Set.of("id", "department_id", "customer_id", "order_date", "total_amount", "status"),
					"customer", Set.of("id", "name", "region"), "employee",
					Set.of("id", "department_id", "name", "email"), "org_department",
					Set.of("id", "name", "region")));
		service = new SqlSecurityService(tablesMapper, properties);
		lenient().when(tablesMapper.getSelectedTablesByAgentId(5L))
			.thenReturn(List.of("sales_order", "customer", "employee", "org_department", "payment", "receivable"));
	}

	@Test
	void validSelect_isAccepted() {
		SqlSecurityDecision decision = service.validateAndPrepare(5L,
				"SELECT o.id, o.total_amount FROM sales_order o WHERE o.status = 'APPROVED'", "mysql", analyst());

		assertEquals(Set.of("sales_order"), decision.tables());
		assertTrue(decision.sql().contains("sales_order"));
	}

	@Test
	void m3StyleCteAndAggregates_remainAccepted() {
		String sql = """
				WITH payment_by_receivable AS (
				  SELECT receivable_id, SUM(amount) AS paid_amount
				  FROM payment
				  WHERE payment_date < '2026-01-01'
				  GROUP BY receivable_id
				)
				SELECT SUM(COALESCE(p.paid_amount, 0)) / NULLIF(SUM(r.receivable_amount), 0) AS collection_rate
				FROM receivable r
				JOIN sales_order so ON so.id = r.order_id
				LEFT JOIN payment_by_receivable p ON p.receivable_id = r.id
				WHERE so.status = 'APPROVED'
				""";

		SqlSecurityDecision decision = service.validateAndPrepare(5L, sql, "mysql", analyst());

		assertTrue(decision.tables().containsAll(Set.of("payment", "receivable", "sales_order")));
	}

	@Test
	void nonSelectAndMultipleStatements_areBlocked() {
		List<String> attacks = List.of("DELETE FROM sales_order", "UPDATE sales_order SET status='X'",
				"INSERT INTO sales_order(id) VALUES (1)", "DROP TABLE sales_order", "CALL dangerous_proc()",
				"SELECT id FROM sales_order; DELETE FROM sales_order");

		for (String attack : attacks) {
			assertThrows(SqlSecurityException.class,
					() -> service.validateAndPrepare(5L, attack, "mysql", analyst()), attack);
		}
	}

	@Test
	void dangerousFunction_isBlocked() {
		SqlSecurityException error = assertThrows(SqlSecurityException.class,
				() -> service.validateAndPrepare(5L, "SELECT SLEEP(5) FROM sales_order", "mysql", analyst()));

		assertTrue(error.getMessage().contains("SQL_SECURITY_FUNCTION"));
	}

	@Test
	void unselectedTable_isBlocked() {
		SqlSecurityException error = assertThrows(SqlSecurityException.class,
				() -> service.validateAndPrepare(5L, "SELECT id FROM secret_payroll", "mysql", analyst()));

		assertTrue(error.getMessage().contains("TABLE_ALLOWLIST"));
	}

	@Test
	void unselectedColumn_isBlocked() {
		SqlSecurityException error = assertThrows(SqlSecurityException.class, () -> service.validateAndPrepare(5L,
				"SELECT o.internal_secret FROM sales_order o", "mysql", analyst()));

		assertTrue(error.getMessage().contains("COLUMN_ALLOWLIST"));
	}

	@Test
	void lockingSelect_isBlocked() {
		SqlSecurityException error = assertThrows(SqlSecurityException.class, () -> service.validateAndPrepare(5L,
				"SELECT id FROM sales_order FOR UPDATE", "mysql", analyst()));

		assertTrue(error.getMessage().contains("READ_ONLY"));
	}

	@Test
	void sensitiveColumn_requiresExistingHumanReviewFlow() {
		assertThrows(SqlHumanReviewRequiredException.class,
				() -> service.validateAndPrepare(5L, "SELECT email FROM employee", "mysql", analyst()));

		SqlSecurityDecision approved = service.validateAndPrepare(5L, "SELECT email FROM employee", "mysql",
				new QuerySecurityContext("reviewer", "ANALYST", List.of(), true));
		assertTrue(approved.selectedColumns().contains("email"));
	}

	@Test
	void departmentRole_injectsAuthorizedDepartmentPredicate() {
		SqlSecurityDecision decision = service.validateAndPrepare(5L,
				"SELECT o.id, o.total_amount FROM sales_order o WHERE o.status = 'APPROVED'", "mysql",
				new QuerySecurityContext("dept-user", "DEPARTMENT_USER", List.of(2L, 3L), false));

		assertTrue(decision.departmentScopeApplied());
		assertTrue(decision.sql().replace(" ", "").contains("o.department_idIN(2,3)"));
	}

	@Test
	void departmentRole_withoutScopeOrAnchor_isBlocked() {
		assertThrows(SqlSecurityException.class,
				() -> service.validateAndPrepare(5L, "SELECT id FROM sales_order", "mysql",
						new QuerySecurityContext("dept-user", "DEPARTMENT_USER", List.of(), false)));
		assertThrows(SqlSecurityException.class,
				() -> service.validateAndPrepare(5L, "SELECT id, name FROM customer", "mysql",
						new QuerySecurityContext("dept-user", "DEPARTMENT_USER", List.of(2L), false)));
	}

	@Test
	void departmentRole_unionCannotUseOneScopedBranchToExposeAnother() {
		String union = "SELECT id FROM sales_order UNION ALL SELECT id FROM customer";

		assertThrows(SqlSecurityException.class,
				() -> service.validateAndPrepare(5L, union, "mysql",
						new QuerySecurityContext("dept-user", "DEPARTMENT_USER", List.of(2L), false)));
	}

	@Test
	void crossJoin_requiresHumanReview() {
		assertThrows(SqlHumanReviewRequiredException.class, () -> service.validateAndPrepare(5L,
				"SELECT o.id, c.id FROM sales_order o CROSS JOIN customer c", "mysql", analyst()));
	}

	@Test
	void sensitiveResult_isMaskedWithoutMutatingNonSensitiveColumns() {
		Map<String, String> row = new LinkedHashMap<>();
		row.put("name", "Synthetic User");
		row.put("email", "synthetic.user@example.test");
		row.put("phone", "13800138000");
		row.put("employee_email", "alias@example.test");
		ResultSetBO resultSet = ResultSetBO.builder().column(List.of("name", "email", "phone", "employee_email"))
			.data(new ArrayList<>(List.of(row)))
			.build();

		ResultSetBO masked = service.maskSensitiveData(resultSet);

		assertEquals("Synthetic User", masked.getData().get(0).get("name"));
		assertEquals("s***@example.test", masked.getData().get(0).get("email"));
		assertEquals("138****8000", masked.getData().get(0).get("phone"));
		assertEquals("a***@example.test", masked.getData().get(0).get("employee_email"));
	}

	private QuerySecurityContext analyst() {
		return new QuerySecurityContext("test-user", "ANALYST", List.of(), false);
	}

}
