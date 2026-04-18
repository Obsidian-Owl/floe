---
name: telemetry
description: "Skill for the Telemetry area of floe. 43 symbols across 11 files."
---

# Telemetry

43 symbols | 11 files | Cohesion: 90%

## When to Use

- Working with code in `packages/`
- Understanding how initialize, configure_propagators, get_ratio work
- Modifying telemetry-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/telemetry/provider.py` | initialize, _get_noop_reason, _build_auth_headers, _setup_meter_provider, __enter__ (+5) |
| `packages/floe-core/src/floe_core/telemetry/propagation.py` | configure_propagators, get_current_span_context, get_trace_id, get_span_id, is_trace_active (+4) |
| `packages/floe-core/src/floe_core/telemetry/tracing.py` | get_tracer, _set_span_attributes, _set_dynamic_attributes, async_wrapper, sync_wrapper (+3) |
| `packages/floe-core/src/floe_core/telemetry/metrics.py` | increment, _get_or_create_counter, set_gauge, _get_or_create_gauge, record_histogram (+1) |
| `packages/floe-core/src/floe_core/schemas/telemetry.py` | get_ratio, get_sampling_ratio |
| `packages/floe-core/src/floe_core/telemetry/tracer_factory.py` | reset_tracer, set_tracer |
| `packages/floe-core/src/floe_core/telemetry/initialization.py` | ensure_telemetry_initialized, reset_telemetry |
| `packages/floe-core/src/floe_core/observability.py` | reset_for_testing |
| `packages/floe-core/src/floe_core/telemetry/logging.py` | configure_logging |
| `packages/floe-core/src/floe_core/cli/main.py` | cli |

## Entry Points

Start here when exploring this area:

- **`initialize`** (Function) — `packages/floe-core/src/floe_core/telemetry/provider.py:210`
- **`configure_propagators`** (Function) — `packages/floe-core/src/floe_core/telemetry/propagation.py:41`
- **`get_ratio`** (Function) — `packages/floe-core/src/floe_core/schemas/telemetry.py:324`
- **`get_sampling_ratio`** (Function) — `packages/floe-core/src/floe_core/schemas/telemetry.py:407`
- **`reset_for_testing`** (Function) — `packages/floe-core/src/floe_core/observability.py:241`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `initialize` | Function | `packages/floe-core/src/floe_core/telemetry/provider.py` | 210 |
| `configure_propagators` | Function | `packages/floe-core/src/floe_core/telemetry/propagation.py` | 41 |
| `get_ratio` | Function | `packages/floe-core/src/floe_core/schemas/telemetry.py` | 324 |
| `get_sampling_ratio` | Function | `packages/floe-core/src/floe_core/schemas/telemetry.py` | 407 |
| `reset_for_testing` | Function | `packages/floe-core/src/floe_core/observability.py` | 241 |
| `reset_tracer` | Function | `packages/floe-core/src/floe_core/telemetry/tracer_factory.py` | 117 |
| `configure_logging` | Function | `packages/floe-core/src/floe_core/telemetry/logging.py` | 71 |
| `ensure_telemetry_initialized` | Function | `packages/floe-core/src/floe_core/telemetry/initialization.py` | 58 |
| `reset_telemetry` | Function | `packages/floe-core/src/floe_core/telemetry/initialization.py` | 172 |
| `cli` | Function | `packages/floe-core/src/floe_core/cli/main.py` | 76 |
| `get_tracer` | Function | `packages/floe-core/src/floe_core/telemetry/tracing.py` | 70 |
| `async_wrapper` | Function | `packages/floe-core/src/floe_core/telemetry/tracing.py` | 200 |
| `sync_wrapper` | Function | `packages/floe-core/src/floe_core/telemetry/tracing.py` | 223 |
| `to_otel_dict` | Function | `packages/floe-core/src/floe_core/telemetry/conventions.py` | 98 |
| `get_current_span_context` | Function | `packages/floe-core/src/floe_core/telemetry/propagation.py` | 234 |
| `get_trace_id` | Function | `packages/floe-core/src/floe_core/telemetry/propagation.py` | 243 |
| `get_span_id` | Function | `packages/floe-core/src/floe_core/telemetry/propagation.py` | 261 |
| `is_trace_active` | Function | `packages/floe-core/src/floe_core/telemetry/propagation.py` | 279 |
| `load_telemetry_backend` | Function | `packages/floe-core/src/floe_core/telemetry/provider.py` | 67 |
| `set_tracer` | Function | `packages/floe-core/src/floe_core/telemetry/tracing.py` | 84 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Compile_command → Get_tracer` | cross_community | 5 |
| `Promote_multi → Get_tracer` | cross_community | 5 |
| `Compile_command → To_otel_dict` | cross_community | 4 |
| `Rollback → Get_tracer` | cross_community | 4 |
| `Promote_multi → To_otel_dict` | cross_community | 4 |
| `Rollback → To_otel_dict` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Oci | 4 calls |
| Schemas | 2 calls |
| Floe_lineage_marquez | 1 calls |

## How to Explore

1. `gitnexus_context({name: "initialize"})` — see callers and callees
2. `gitnexus_query({query: "telemetry"})` — find related execution flows
3. Read key files listed above for implementation details
