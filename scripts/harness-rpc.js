#!/usr/bin/env node
"use strict";

/**
 * harness-rpc.js
 *
 * Minimal RPC-style CLI for the hybrid harness APIs.
 *
 * Examples:
 *   harness-rpc.js plan --query "fix continue hang"
 *   harness-rpc.js session-start --query "debug switchboard"
 *   harness-rpc.js session-advance --id <session_id> --action pass --note "discover complete"
 *   harness-rpc.js session-tree --include-completed true
 *   harness-rpc.js review --response "done" --criteria "headers,smoke"
 *   harness-rpc.js run-start --query "implement parity features" --safety-mode execute-mutating
 *   harness-rpc.js run-event --id <session_id> --event-type tool_call --risk-class review-required --approved true
 *   harness-rpc.js run-replay --id <session_id>
 */

const DEFAULT_BASE_URL = process.env.HYB_URL || "http://127.0.0.1:8003";
const API_KEY = process.env.HYBRID_API_KEY || "";

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token.startsWith("--")) {
      const key = token.slice(2);
      const next = argv[i + 1];
      if (!next || next.startsWith("--")) {
        args[key] = true;
      } else {
        args[key] = next;
        i += 1;
      }
    } else {
      args._.push(token);
    }
  }
  return args;
}

async function call(path, method = "GET", body = null) {
  const headers = { "Content-Type": "application/json" };
  if (API_KEY) headers["X-API-Key"] = API_KEY;
  const resp = await fetch(`${DEFAULT_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    console.error(JSON.stringify({ ok: false, status: resp.status, error: payload }, null, 2));
    process.exit(1);
  }
  console.log(JSON.stringify({ ok: true, status: resp.status, data: payload }, null, 2));
}

function csv(value) {
  if (!value) return [];
  return String(value)
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cmd = args._[0];
  if (!cmd) {
    console.error("Usage: harness-rpc.js <command> [--flags]");
    process.exit(2);
  }

  switch (cmd) {
    case "plan":
      return call("/workflow/plan", "POST", { query: args.query || args.q || "" });
    case "session-start":
      return call("/workflow/session/start", "POST", { query: args.query || args.q || "" });
    case "session-list":
      return call("/workflow/sessions", "GET");
    case "session-tree": {
      const includeCompleted = args["include-completed"] ?? "true";
      const includeFailed = args["include-failed"] ?? "true";
      const includeObjective = args["include-objective"] ?? "true";
      return call(
        `/workflow/tree?include_completed=${includeCompleted}&include_failed=${includeFailed}&include_objective=${includeObjective}`,
        "GET",
      );
    }
    case "session-get":
      return call(`/workflow/session/${args.id}${args.lineage ? "?lineage=true" : ""}`, "GET");
    case "session-fork":
      return call(`/workflow/session/${args.id}/fork`, "POST", { note: args.note || "forked session" });
    case "session-advance":
      return call(`/workflow/session/${args.id}/advance`, "POST", {
        action: args.action || "note",
        note: args.note || "",
      });
    case "review":
      return call("/review/acceptance", "POST", {
        response: args.response || "",
        query: args.query || "",
        criteria: csv(args.criteria),
        expected_keywords: csv(args.keywords),
        min_criteria_ratio: args.minCriteria ? Number(args.minCriteria) : 0.7,
        min_keyword_ratio: args.minKeywords ? Number(args.minKeywords) : 0.6,
        run_harness_eval: args.eval === "true" || args.eval === true,
      });
    case "eval":
      return call("/harness/eval", "POST", {
        query: args.query || "",
        mode: args.mode || "auto",
        expected_keywords: csv(args.keywords),
      });
    case "run-start":
      return call("/workflow/run/start", "POST", {
        query: args.query || args.q || "",
        safety_mode: args["safety-mode"] || "plan-readonly",
        token_limit: args["token-limit"] ? Number(args["token-limit"]) : 8000,
        tool_call_limit: args["tool-call-limit"] ? Number(args["tool-call-limit"]) : 40,
      });
    case "run-get":
      return call(`/workflow/run/${args.id}?replay=${args.replay ? "true" : "false"}`, "GET");
    case "run-mode":
      return call(`/workflow/run/${args.id}/mode`, "POST", {
        safety_mode: args["safety-mode"] || "plan-readonly",
        confirm: args.confirm === "true" || args.confirm === true,
      });
    case "run-isolation-get":
      return call(`/workflow/run/${args.id}/isolation`, "GET");
    case "run-isolation-set":
      return call(`/workflow/run/${args.id}/isolation`, "POST", {
        profile: args.profile || "",
        workspace_root: args["workspace-root"] || "",
        network_policy: args["network-policy"] || "",
      });
    case "run-event":
      return call(`/workflow/run/${args.id}/event`, "POST", {
        event_type: args["event-type"] || "event",
        risk_class: args["risk-class"] || "safe",
        approved: args.approved === "true" || args.approved === true,
        token_delta: args["token-delta"] ? Number(args["token-delta"]) : 0,
        tool_call_delta: args["tool-call-delta"] ? Number(args["tool-call-delta"]) : 0,
        detail: args.detail || "",
      });
    case "run-replay":
      return call(`/workflow/run/${args.id}/replay`, "GET");
    case "blueprints":
      return call("/workflow/blueprints", "GET");
    case "parity-scorecard":
      return call("/parity/scorecard", "GET");
    case "runtime-register":
      return call("/control/runtimes/register", "POST", {
        runtime_id: args.id || "",
        name: args.name || "",
        profile: args.profile || "default",
        status: args.status || "ready",
        runtime_class: args["runtime-class"] || "generic",
        transport: args.transport || "http",
        endpoint_env_var: args["endpoint-env-var"] || "",
        tags: csv(args.tags),
      });
    case "runtime-list":
      return call("/control/runtimes", "GET");
    case "runtime-get":
      return call(`/control/runtimes/${args.id}`, "GET");
    case "runtime-status":
      return call(`/control/runtimes/${args.id}/status`, "POST", {
        status: args.status || "ready",
        note: args.note || "",
      });
    case "runtime-deploy":
      return call(`/control/runtimes/${args.id}/deployments`, "POST", {
        deployment_id: args["deployment-id"] || "",
        version: args.version || "",
        profile: args.profile || "default",
        target: args.target || "local",
        status: args.status || "deployed",
        note: args.note || "",
      });
    case "runtime-rollback":
      return call(`/control/runtimes/${args.id}/rollback`, "POST", {
        to_deployment_id: args["to-deployment-id"] || "",
        reason: args.reason || "",
      });
    case "runtime-schedule-policy":
      return call("/control/runtimes/schedule/policy", "GET");
    case "runtime-schedule":
      return call("/control/runtimes/schedule/select", "POST", {
        objective: args.objective || args.query || "",
        strategy: args.strategy || "weighted",
        include_degraded: args["include-degraded"] === "true" || args["include-degraded"] === true,
        requirements: {
          runtime_class: args["runtime-class"] || "",
          transport: args.transport || "",
          tags: csv(args.tags),
        },
      });
    default:
      console.error(`Unknown command: ${cmd}`);
      process.exit(2);
  }
}

main().catch((err) => {
  console.error(JSON.stringify({ ok: false, error: String(err) }, null, 2));
  process.exit(1);
});
