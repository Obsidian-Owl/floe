---
name: base-classes
description: "Skill for the Base_classes area of floe. 126 symbols across 17 files."
---

# Base_classes

126 symbols | 17 files | Cohesion: 90%

## When to Use

- Working with code in `testing/`
- Understanding how test_health_check_returns_health_status, test_health_check_unhealthy_before_startup, test_health_check_returns_health_status work
- Modifying base_classes-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `testing/base_classes/base_rbac_plugin_tests.py` | test_generate_pod_security_context_has_run_as_non_root, test_generate_pod_security_context_has_run_as_user, test_generate_container_security_context_has_no_privilege_escalation, test_generate_container_security_context_drops_all_capabilities, test_generate_pod_security_context_has_seccomp_profile (+24) |
| `testing/base_classes/base_secrets_plugin_tests.py` | test_health_check_returns_health_status, test_get_secret_returns_value_or_none, test_set_secret_creates_or_updates, test_list_secrets_returns_list, test_list_secrets_filters_by_prefix (+13) |
| `testing/base_classes/base_health_check_tests.py` | test_health_check_returns_health_status, test_health_check_reports_healthy_when_connected, test_health_check_reports_unhealthy_when_not_connected, test_health_check_includes_response_time, test_health_check_completes_within_one_second (+8) |
| `testing/base_classes/golden_test_utils.py` | GoldenFixture, __post_init__, _calculate_checksum, save, verify_integrity (+5) |
| `testing/base_classes/plugin_lifecycle_tests.py` | test_health_check_returns_health_status, test_health_check_unhealthy_before_startup, test_shutdown_can_be_called_without_startup, test_shutdown_can_be_called_multiple_times, test_can_restart_after_shutdown (+2) |
| `packages/floe-core/src/floe_core/schemas/rbac.py` | PodSecurityConfig, RoleBindingSubject, RoleBindingConfig, ServiceAccountConfig, RoleConfig (+2) |
| `testing/base_classes/plugin_discovery_tests.py` | create_plugin_instance, test_plugin_can_be_instantiated, test_instantiated_plugin_has_correct_name, test_plugin_has_required_metadata_attributes, test_plugin_metadata_values_not_none (+2) |
| `testing/base_classes/base_identity_plugin_tests.py` | test_health_check_returns_health_status, test_config_schema_returns_valid_type, test_validate_token_returns_result, test_invalid_token_returns_invalid_result, test_authenticate_returns_token_or_none (+1) |
| `packages/floe-core/src/floe_core/plugins/rbac.py` | generate_pod_security_context, generate_role_binding, generate_service_account, generate_role, generate_namespace |
| `testing/base_classes/integration_test_base.py` | setup_method, check_infrastructure, IntegrationTestBase, teardown_method, _cleanup_namespace |

## Entry Points

Start here when exploring this area:

- **`test_health_check_returns_health_status`** (Function) — `testing/base_classes/plugin_lifecycle_tests.py:140`
- **`test_health_check_unhealthy_before_startup`** (Function) — `testing/base_classes/plugin_lifecycle_tests.py:149`
- **`test_health_check_returns_health_status`** (Function) — `testing/base_classes/base_secrets_plugin_tests.py:249`
- **`test_health_check_returns_health_status`** (Function) — `testing/base_classes/base_identity_plugin_tests.py:212`
- **`test_health_check_returns_health_status`** (Function) — `testing/base_classes/base_health_check_tests.py:107`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `GoldenFixture` | Class | `testing/base_classes/golden_test_utils.py` | 43 |
| `PodSecurityConfig` | Class | `packages/floe-core/src/floe_core/schemas/rbac.py` | 560 |
| `RoleBindingSubject` | Class | `packages/floe-core/src/floe_core/schemas/rbac.py` | 234 |
| `RoleBindingConfig` | Class | `packages/floe-core/src/floe_core/schemas/rbac.py` | 265 |
| `ServiceAccountConfig` | Class | `packages/floe-core/src/floe_core/schemas/rbac.py` | 33 |
| `RoleConfig` | Class | `packages/floe-core/src/floe_core/schemas/rbac.py` | 161 |
| `RoleRule` | Class | `packages/floe-core/src/floe_core/schemas/rbac.py` | 102 |
| `NamespaceConfig` | Class | `packages/floe-core/src/floe_core/schemas/rbac.py` | 388 |
| `PluginTestBase` | Class | `testing/base_classes/plugin_test_base.py` | 23 |
| `IntegrationTestBase` | Class | `testing/base_classes/integration_test_base.py` | 39 |
| `AdapterTestBase` | Class | `testing/base_classes/adapter_test_base.py` | 24 |
| `AuditLogCapture` | Class | `testing/base_classes/base_secrets_plugin_tests.py` | 427 |
| `test_health_check_returns_health_status` | Function | `testing/base_classes/plugin_lifecycle_tests.py` | 140 |
| `test_health_check_unhealthy_before_startup` | Function | `testing/base_classes/plugin_lifecycle_tests.py` | 149 |
| `test_health_check_returns_health_status` | Function | `testing/base_classes/base_secrets_plugin_tests.py` | 249 |
| `test_health_check_returns_health_status` | Function | `testing/base_classes/base_identity_plugin_tests.py` | 212 |
| `test_health_check_returns_health_status` | Function | `testing/base_classes/base_health_check_tests.py` | 107 |
| `test_health_check_reports_healthy_when_connected` | Function | `testing/base_classes/base_health_check_tests.py` | 118 |
| `test_health_check_reports_unhealthy_when_not_connected` | Function | `testing/base_classes/base_health_check_tests.py` | 128 |
| `test_health_check_includes_response_time` | Function | `testing/base_classes/base_health_check_tests.py` | 144 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Schemas | 2 calls |
| Helm | 1 calls |
| Floe_catalog_polaris | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_health_check_returns_health_status"})` — see callers and callees
2. `gitnexus_query({query: "base_classes"})` — find related execution flows
3. Read key files listed above for implementation details
