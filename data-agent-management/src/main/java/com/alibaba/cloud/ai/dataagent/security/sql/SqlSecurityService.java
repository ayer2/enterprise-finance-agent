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

import com.alibaba.cloud.ai.dataagent.bo.schema.ResultSetBO;
import com.alibaba.cloud.ai.dataagent.mapper.AgentDatasourceTablesMapper;
import com.alibaba.cloud.ai.dataagent.properties.DataAgentProperties;
import com.alibaba.druid.DbType;
import com.alibaba.druid.sql.SQLUtils;
import com.alibaba.druid.sql.ast.SQLStatement;
import com.alibaba.druid.sql.ast.expr.SQLMethodInvokeExpr;
import com.alibaba.druid.sql.ast.statement.SQLExprTableSource;
import com.alibaba.druid.sql.ast.statement.SQLJoinTableSource;
import com.alibaba.druid.sql.ast.statement.SQLSelectQueryBlock;
import com.alibaba.druid.sql.ast.statement.SQLSelectStatement;
import com.alibaba.druid.sql.ast.statement.SQLTableSource;
import com.alibaba.druid.sql.visitor.SQLASTVisitorAdapter;
import com.alibaba.druid.sql.visitor.SchemaStatVisitor;
import com.alibaba.druid.stat.TableStat;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

/** AST-based SQL security boundary applied immediately before database execution. */
@Service
@RequiredArgsConstructor
public class SqlSecurityService {

	private final AgentDatasourceTablesMapper tablesMapper;

	private final DataAgentProperties properties;

	public SqlSecurityDecision validateAndPrepare(long agentId, String sql, String dialect,
			QuerySecurityContext context) {
		DataAgentProperties.SqlSecurity policy = properties.getSqlSecurity();
		if (!policy.isEnabled()) {
			return new SqlSecurityDecision(sql, Set.of(), Set.of(), false);
		}
		DbType dbType = resolveDbType(dialect);
		List<SQLStatement> statements;
		try {
			statements = SQLUtils.parseStatements(sql, dbType);
		}
		catch (RuntimeException ex) {
			throw new SqlSecurityException("SQL_SECURITY_PARSE_ERROR: SQL cannot be parsed for the configured dialect");
		}
		if (statements.size() != 1) {
			throw new SqlSecurityException("SQL_SECURITY_SINGLE_STATEMENT: exactly one statement is required");
		}
		if (!(statements.get(0) instanceof SQLSelectStatement selectStatement)) {
			throw new SqlSecurityException("SQL_SECURITY_READ_ONLY: only SELECT statements are allowed");
		}

		AstFacts facts = inspect(selectStatement, dbType);
		if (facts.hasSelectInto || facts.hasForUpdate) {
			throw new SqlSecurityException("SQL_SECURITY_READ_ONLY: SELECT INTO and locking SELECT are not allowed");
		}
		Set<String> dangerousFunctions = normalize(policy.getDangerousFunctions());
		Set<String> blockedFunctions = facts.functions.stream()
			.filter(dangerousFunctions::contains)
			.collect(Collectors.toCollection(LinkedHashSet::new));
		if (!blockedFunctions.isEmpty()) {
			throw new SqlSecurityException("SQL_SECURITY_FUNCTION: dangerous function blocked: " + blockedFunctions);
		}

		Set<String> allowedTables = normalize(tablesMapper.getSelectedTablesByAgentId(agentId));
		if (allowedTables.isEmpty()) {
			throw new SqlSecurityException("SQL_SECURITY_TABLE_ALLOWLIST: the Agent has no enabled tables");
		}
		Set<String> deniedTables = new LinkedHashSet<>(facts.tables);
		deniedTables.removeAll(allowedTables);
		if (!deniedTables.isEmpty()) {
			throw new SqlSecurityException("SQL_SECURITY_TABLE_ALLOWLIST: table is not enabled for this Agent: "
					+ deniedTables);
		}

		validateColumns(facts, policy.getAllowedColumns());
		Set<String> sensitive = normalize(policy.getSensitiveColumns());
		Set<String> selectedSensitiveColumns = facts.selectedColumns.stream()
			.filter(sensitive::contains)
			.collect(Collectors.toCollection(LinkedHashSet::new));
		boolean highCost = facts.crossJoin || facts.tables.size() >= 5;
		if ((!selectedSensitiveColumns.isEmpty() || highCost) && !context.humanReviewed()) {
			throw new SqlHumanReviewRequiredException(
					"SQL_HUMAN_REVIEW_REQUIRED: sensitive or high-cost query must be submitted with humanFeedback=true");
		}

		boolean departmentScopeApplied = applyDepartmentScope(selectStatement, facts, dbType, context,
				policy.getDepartmentScopedTables());
		return new SqlSecurityDecision(SQLUtils.toSQLString(selectStatement, dbType), Set.copyOf(facts.tables),
				Set.copyOf(facts.selectedColumns), departmentScopeApplied);
	}

	public ResultSetBO maskSensitiveData(ResultSetBO resultSet) {
		if (resultSet == null || resultSet.getData() == null) {
			return resultSet;
		}
		Set<String> sensitive = normalize(properties.getSqlSecurity().getSensitiveColumns());
		List<Map<String, String>> maskedRows = new ArrayList<>(resultSet.getData().size());
		for (Map<String, String> row : resultSet.getData()) {
			Map<String, String> masked = new LinkedHashMap<>(row);
			masked.replaceAll((column, value) -> shouldMask(column, value, sensitive) ? mask(value) : value);
			maskedRows.add(masked);
		}
		resultSet.setData(maskedRows);
		return resultSet;
	}

	private AstFacts inspect(SQLSelectStatement statement, DbType dbType) {
		SchemaStatVisitor schemaVisitor = SQLUtils.createSchemaStatVisitor(dbType);
		statement.accept(schemaVisitor);
		AstFacts facts = new AstFacts();
		facts.tables.addAll(schemaVisitor.getTables().keySet().stream()
			.map(TableStat.Name::getName)
			.map(SqlSecurityService::normalizeIdentifier)
			.toList());
		for (TableStat.Column column : schemaVisitor.getColumns()) {
			String name = normalizeIdentifier(column.getName());
			if (!name.isBlank() && !"*".equals(name)) {
				facts.columns.add(new ColumnReference(normalizeIdentifier(column.getTable()), name));
				if (column.isSelect()) {
					facts.selectedColumns.add(name);
				}
			}
		}
		facts.functions.addAll(schemaVisitor.getFunctions().stream()
			.map(SQLMethodInvokeExpr::getMethodName)
			.map(SqlSecurityService::normalizeIdentifier)
			.toList());
		statement.accept(new SQLASTVisitorAdapter() {
			@Override
			public boolean visit(SQLExprTableSource tableSource) {
				String table = normalizeIdentifier(tableSource.getTableName());
				String alias = normalizeIdentifier(tableSource.getAlias());
				facts.aliasToTable.put(alias.isBlank() ? table : alias, table);
				return true;
			}

			@Override
			public boolean visit(SQLJoinTableSource join) {
				if (join.getJoinType() == SQLJoinTableSource.JoinType.CROSS_JOIN
						|| join.getJoinType() == SQLJoinTableSource.JoinType.COMMA) {
					facts.crossJoin = true;
				}
				return true;
			}

			@Override
			public boolean visit(SQLSelectQueryBlock queryBlock) {
				facts.hasSelectInto |= queryBlock.getInto() != null;
				facts.hasForUpdate |= queryBlock.isForUpdate();
				return true;
			}
		});
		return facts;
	}

	private void validateColumns(AstFacts facts, Map<String, Set<String>> configuredColumns) {
		if (configuredColumns == null || configuredColumns.isEmpty()) {
			return;
		}
		Map<String, Set<String>> allowlist = new HashMap<>();
		configuredColumns.forEach((table, columns) -> allowlist.put(normalizeIdentifier(table), normalize(columns)));
		for (ColumnReference column : facts.columns) {
			String table = facts.aliasToTable.getOrDefault(column.table(), column.table());
			if (!table.isBlank() && allowlist.containsKey(table)) {
				if (!allowlist.get(table).contains(column.column())) {
					throw new SqlSecurityException("SQL_SECURITY_COLUMN_ALLOWLIST: column is not enabled: " + table + "."
							+ column.column());
				}
			}
			else if (table.isBlank() && facts.tables.stream().anyMatch(allowlist::containsKey)
					&& facts.tables.stream().filter(allowlist::containsKey)
						.noneMatch(candidate -> allowlist.get(candidate).contains(column.column()))) {
				throw new SqlSecurityException(
						"SQL_SECURITY_COLUMN_ALLOWLIST: unqualified column is not enabled: " + column.column());
			}
		}
	}

	private boolean applyDepartmentScope(SQLSelectStatement statement, AstFacts facts, DbType dbType,
			QuerySecurityContext context, Set<String> configuredScopedTables) {
		if (!context.isDepartmentScoped()) {
			return false;
		}
		if (context.departmentIds().isEmpty()) {
			throw new SqlSecurityException("SQL_SECURITY_DATA_SCOPE: DEPARTMENT_USER requires departmentIds");
		}
		Set<String> scopedTables = normalize(configuredScopedTables);
		if (!(statement.getSelect().getQuery() instanceof SQLSelectQueryBlock queryBlock)) {
			throw new SqlSecurityException(
					"SQL_SECURITY_DATA_SCOPE: set operations require an administrator or a pre-scoped database view");
		}
		Map<String, String> visibleTables = new LinkedHashMap<>();
		collectVisibleTables(queryBlock.getFrom(), visibleTables);
		String scopedTable = visibleTables.keySet().stream().filter(scopedTables::contains).findFirst()
			.orElseThrow(() -> new SqlSecurityException(
					"SQL_SECURITY_DATA_SCOPE: query cannot be safely anchored to a department-scoped table"));
		String qualifier = visibleTables.get(scopedTable);
		String departmentList = context.departmentIds().stream().map(String::valueOf).collect(Collectors.joining(","));
		statement.addWhere(SQLUtils.toSQLExpr(qualifier + ".department_id IN (" + departmentList + ")", dbType));
		return true;
	}

	private static void collectVisibleTables(SQLTableSource tableSource, Map<String, String> visibleTables) {
		if (tableSource instanceof SQLExprTableSource expressionTable) {
			String table = normalizeIdentifier(expressionTable.getTableName());
			String alias = normalizeIdentifier(expressionTable.getAlias());
			visibleTables.putIfAbsent(table, alias.isBlank() ? table : alias);
		}
		else if (tableSource instanceof SQLJoinTableSource join) {
			collectVisibleTables(join.getLeft(), visibleTables);
			collectVisibleTables(join.getRight(), visibleTables);
		}
	}

	private static String mask(String value) {
		if (value == null || value.isBlank()) {
			return value;
		}
		int at = value.indexOf('@');
		if (at > 0) {
			String local = value.substring(0, at);
			return local.substring(0, 1) + "***" + value.substring(at);
		}
		String digits = value.replaceAll("\\D", "");
		if (digits.length() >= 7) {
			return value.substring(0, Math.min(3, value.length())) + "****"
					+ value.substring(Math.max(value.length() - 4, 3));
		}
		return "***";
	}

	private static boolean shouldMask(String column, String value, Set<String> sensitiveColumns) {
		String normalizedColumn = normalizeIdentifier(column);
		boolean sensitiveName = sensitiveColumns.stream()
			.anyMatch(sensitive -> normalizedColumn.equals(sensitive) || normalizedColumn.endsWith("_" + sensitive));
		if (sensitiveName || value == null) {
			return sensitiveName;
		}
		int at = value.indexOf('@');
		if (at > 0 && at < value.length() - 3 && value.indexOf('.', at) > at + 1) {
			return true;
		}
		return value.replaceAll("\\D", "").length() == 11;
	}

	private static Set<String> normalize(Collection<String> values) {
		if (values == null) {
			return Set.of();
		}
		return values.stream().map(SqlSecurityService::normalizeIdentifier).filter(value -> !value.isBlank())
			.collect(Collectors.toCollection(LinkedHashSet::new));
	}

	private static String normalizeIdentifier(String identifier) {
		if (identifier == null) {
			return "";
		}
		String normalized = identifier.replace("`", "").replace("\"", "").trim().toLowerCase(Locale.ROOT);
		int dot = normalized.lastIndexOf('.');
		return dot >= 0 ? normalized.substring(dot + 1) : normalized;
	}

	private static DbType resolveDbType(String dialect) {
		String normalized = dialect == null ? "" : dialect.toLowerCase(Locale.ROOT);
		if ("dameng".equals(normalized)) {
			return DbType.dm;
		}
		DbType resolved = DbType.of(normalized);
		return resolved != null ? resolved : DbType.mysql;
	}

	private record ColumnReference(String table, String column) {
	}

	private static final class AstFacts {

		private final Set<String> tables = new LinkedHashSet<>();

		private final Set<ColumnReference> columns = new LinkedHashSet<>();

		private final Set<String> selectedColumns = new LinkedHashSet<>();

		private final Set<String> functions = new HashSet<>();

		private final Map<String, String> aliasToTable = new HashMap<>();

		private boolean crossJoin;

		private boolean hasSelectInto;

		private boolean hasForUpdate;

	}

}
