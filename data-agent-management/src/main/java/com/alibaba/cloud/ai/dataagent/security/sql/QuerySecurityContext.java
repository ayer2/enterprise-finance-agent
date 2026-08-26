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

import java.util.List;

/** Security attributes carried with one Agent query. */
public record QuerySecurityContext(String actorId, String role, List<Long> departmentIds, boolean humanReviewed) {

	public QuerySecurityContext {
		actorId = actorId == null || actorId.isBlank() ? "anonymous" : actorId;
		role = role == null || role.isBlank() ? "ANALYST" : role.trim().toUpperCase();
		departmentIds = departmentIds == null ? List.of() : departmentIds.stream().distinct().sorted().toList();
	}

	public boolean isDepartmentScoped() {
		return "DEPARTMENT_USER".equals(role);
	}

}
