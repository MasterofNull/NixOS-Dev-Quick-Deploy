#!/usr/bin/env node
"use strict";

/**
 * harness-rpc.js
 *
 * Minimal RPC-style CLI for the hybrid harness APIs.
 *
 * Bootstrap (run first on every session):
 *   harness-rpc.js status            # verify harness is running
 *   harness-rpc.js hints -q "task"  # get workflow hints
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
 *
 * Environment:
 *   HYBRID_URL (or HYB_URL)  — harness base URL (default: http://127.0.0.1:8003)
 *   HYBRID_API_KEY           — optional API key for auth
 */

const DEFAULT_BASE_URL =
  process.env.HYBRID_URL || process.env.HYB_URL || "http://127.0.0.1:8003";
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
    console.error(
      JSON.stringify(
        { ok: false, status: resp.status, error: payload },
        null,
        2
      )
    );
    process.exit(1);
  }
  console.log(
    JSON.stringify({ ok: true, status: resp.status, data: payload }, null, 2)
  );
}

function csv(value) {
  if (!value) return [];
  return String(value)
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

function defaultIntentContract(query) {
  const normalized = String(query || "").trim() || "workflow run";
  return {
    user_intent: normalized,
    definition_of_done: `Complete requested workflow task: ${normalized.slice(
      0,
      120
    )}`,
    depth_expectation: "minimum",
    spirit_constraints: [
      "follow declarative-first policy",
      "capture validation evidence",
      "prefer harness retrieval, memory recall, and periodic compaction over resending long prompt history",
    ],
    no_early_exit_without: [
      "all requested checks complete",
      "context strategy or blocker documented when the task is long-running",
    ],
  };
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
      return call("/workflow/plan", "POST", {
        query: args.query || args.q || "",
      });
    case "session-start":
      return call("/workflow/session/start", "POST", {
        query: args.query || args.q || "",
      });
    case "session-list":
      return call("/workflow/sessions", "GET");
    case "session-tree": {
      const includeCompleted = args["include-completed"] ?? "true";
      const includeFailed = args["include-failed"] ?? "true";
      const includeObjective = args["include-objective"] ?? "true";
      return call(
        `/workflow/tree?include_completed=${includeCompleted}&include_failed=${includeFailed}&include_objective=${includeObjective}`,
        "GET"
      );
    }
    case "session-get":
      return call(
        `/workflow/session/${args.id}${args.lineage ? "?lineage=true" : ""}`,
        "GET"
      );
    case "session-fork":
      return call(`/workflow/session/${args.id}/fork`, "POST", {
        note: args.note || "forked session",
      });
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
    case "run-start": {
      const query = args.query || args.q || "";
      const intentContract = defaultIntentContract(query);
      if (args["intent-user"])
        intentContract.user_intent = String(args["intent-user"]);
      if (args["intent-dod"])
        intentContract.definition_of_done = String(args["intent-dod"]);
      if (args["intent-depth"])
        intentContract.depth_expectation = String(args["intent-depth"]);
      const spirit = csv(args["intent-spirit"]);
      if (spirit.length > 0) intentContract.spirit_constraints = spirit;
      const noExit = csv(args["intent-no-exit"]);
      if (noExit.length > 0) intentContract.no_early_exit_without = noExit;
      return call("/workflow/run/start", "POST", {
        query,
        safety_mode: args["safety-mode"] || "plan-readonly",
        token_limit: args["token-limit"] ? Number(args["token-limit"]) : 8000,
        tool_call_limit: args["tool-call-limit"]
          ? Number(args["tool-call-limit"])
          : 40,
        requesting_agent: args.agent || "human",
        requester_role: args["requester-role"] || "orchestrator",
        intent_contract: intentContract,
      });
    }
    case "run-get":
      return call(
        `/workflow/run/${args.id}?replay=${args.replay ? "true" : "false"}`,
        "GET"
      );
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
        tool_call_delta: args["tool-call-delta"]
          ? Number(args["tool-call-delta"])
          : 0,
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
        include_degraded:
          args["include-degraded"] === "true" ||
          args["include-degraded"] === true,
        requirements: {
          runtime_class: args["runtime-class"] || "",
          transport: args.transport || "",
          tags: csv(args.tags),
        },
      });
    case "coordinator-status":
      return call("/control/ai-coordinator/status", "GET");
    case "coordinator-skills":
      return call(
        `/control/ai-coordinator/skills?limit=${args.limit || 25}`,
        "GET"
      );
    case "coordinator-delegate":
      return call("/control/ai-coordinator/delegate", "POST", {
        task: args.task || args.query || args.q || "",
        profile: args.profile || "",
        max_tokens: args["max-tokens"] ? Number(args["max-tokens"]) : undefined,
        temperature: args.temperature ? Number(args.temperature) : undefined,
      });

    // ── Sub-agent delegation ─────────────────────────────────────────────
    case "sub-agent":
    case "spawn":
    case "delegate": {
      // Spawns a task through the harness workflow system with its own run/session
      const spawnQuery = args.task || args.query || args.q || "";
      const spawnIntent = {
        user_intent:
          args["intent-user"] || `Complete: ${spawnQuery.slice(0, 120)}`,
        definition_of_done:
          args["intent-dod"] || "Task completed with validation evidence",
        depth_expectation: args["intent-depth"] || "standard",
        spirit_constraints: ["follow project conventions", "capture evidence"],
        no_early_exit_without: ["validation passes"],
      };
      return call("/workflow/run/start", "POST", {
        query: spawnQuery,
        safety_mode: args["safety-mode"] || "execute-mutating",
        token_limit: args["token-limit"] ? Number(args["token-limit"]) : 4000,
        tool_call_limit: args["tool-call-limit"]
          ? Number(args["tool-call-limit"])
          : 20,
        requesting_agent: args.agent || "human",
        requester_role: args["requester-role"] || "orchestrator",
        intent_contract: spawnIntent,
      });
    }
    case "orchestrate":
      return call("/workflow/orchestrate", "POST", {
        task: args.task || args.query || args.q || "",
        priority: args.priority || "normal",
        agent: args.agent || "codex",
      });
    case "query":
      return call("/query", "POST", {
        query: args.query || args.q || "",
        context: args.context || "",
        max_tokens: args["max-tokens"] ? Number(args["max-tokens"]) : undefined,
      });
    case "web-research":
      return call("/research/web/fetch", "POST", {
        urls: csv(args.urls),
        selectors: csv(args.selectors),
        max_text_chars: args["max-text-chars"]
          ? Number(args["max-text-chars"])
          : undefined,
      });
    case "browser-research":
      return call("/research/web/browser-fetch", "POST", {
        urls: csv(args.urls),
        selectors: csv(args.selectors),
        max_text_chars: args["max-text-chars"]
          ? Number(args["max-text-chars"])
          : undefined,
      });
    case "curated-research":
      return call("/research/workflows/curated-fetch", "POST", {
        workflow: args.workflow || args.pack || "",
        inputs: args.inputs ? JSON.parse(args.inputs) : undefined,
        max_text_chars: args["max-text-chars"]
          ? Number(args["max-text-chars"])
          : undefined,
      });

    // ── Harness bootstrap / health ─────────────────────────────────────────
    case "status":
    case "health":
      return call("/health", "GET");
    case "health-detailed":
      return call("/health/detailed", "GET");
    case "hints":
      return call("/hints", "POST", {
        q: args.query || args.q || "",
        agent: args.agent || "codex",
        format: args.format || "json",
      });

    // ── Agent status / availability ─────────────────────────────────────
    case "agent-status":
      return call(
        `/agent-status${
          args.agent ? "?agent_id=" + encodeURIComponent(args.agent) : ""
        }${args.detail ? "&detail=true" : ""}`,
        "GET"
      );

    // ── Delegation with failover chain (Phase 20.2) ─────────────────────
    case "delegate":
    case "delegate-with-failover":
      return call("/control/ai-coordinator/delegate", "POST", {
        task: args.task || args.query || args.q || "",
        profile: args.profile || "",
        prefer_local:
          args["prefer-local"] === "true" || args["prefer-local"] === true,
        max_tokens: args["max-tokens"] ? Number(args["max-tokens"]) : undefined,
        temperature: args.temperature ? Number(args.temperature) : undefined,
        timeout_s: args.timeout ? Number(args.timeout) : undefined,
        // Phase 20.2: Failover chain is automatic on unavailability
        // The endpoint builds priority-based fallback chains automatically
      });

    // ── Tmux-based agent sandboxes (IndyDevDan pattern) ───────────────────
    case "tmux-spawn": {
      // Spawn a Claude Code agent in an isolated tmux pane
      const tmuxSession = args.session || "agent-sandbox";
      const tmuxWindow = args.window || `agent-${Date.now()}`;
      const agentCmd = args.command || `claude --dangerously-skip-permissions`;
      const task = args.task || args.query || args.q || "";
      const { execSync } = require("child_process");

      try {
        // Create tmux session if it doesn't exist
        try {
          execSync(`tmux has-session -t ${tmuxSession} 2>/dev/null`, {
            encoding: "utf8",
          });
        } catch {
          execSync(`tmux new-session -d -s ${tmuxSession}`, {
            encoding: "utf8",
          });
        }
        // Create new window with the agent command
        execSync(
          `tmux new-window -t ${tmuxSession} -n ${tmuxWindow} "${agentCmd}"`,
          { encoding: "utf8" }
        );
        // If task provided, send it to the pane
        if (task) {
          execSync(
            `tmux send-keys -t ${tmuxSession}:${tmuxWindow} "${task.replace(
              /"/g,
              '\\"'
            )}" Enter`,
            { encoding: "utf8" }
          );
        }
        console.log(
          JSON.stringify(
            {
              ok: true,
              status: 200,
              data: {
                tmux_session: tmuxSession,
                tmux_window: tmuxWindow,
                agent_command: agentCmd,
                task: task || "(none)",
                attach_command: `tmux attach -t ${tmuxSession}:${tmuxWindow}`,
              },
            },
            null,
            2
          )
        );
      } catch (err) {
        console.error(
          JSON.stringify({ ok: false, error: String(err) }, null, 2)
        );
        process.exit(1);
      }
      return;
    }
    case "tmux-list": {
      const { execSync } = require("child_process");
      try {
        const output = execSync(
          "tmux list-windows -a 2>/dev/null || echo '(no tmux sessions)'",
          {
            encoding: "utf8",
          }
        );
        console.log(
          JSON.stringify(
            {
              ok: true,
              status: 200,
              data: { windows: output.trim().split("\n") },
            },
            null,
            2
          )
        );
      } catch (err) {
        console.log(
          JSON.stringify(
            {
              ok: true,
              status: 200,
              data: { windows: [], note: "no tmux sessions" },
            },
            null,
            2
          )
        );
      }
      return;
    }
    case "tmux-kill": {
      const { execSync } = require("child_process");
      const target = args.window || args.session;
      if (!target) {
        console.error(
          JSON.stringify(
            { ok: false, error: "--window or --session required" },
            null,
            2
          )
        );
        process.exit(1);
      }
      try {
        execSync(
          `tmux kill-window -t ${target} 2>/dev/null || tmux kill-session -t ${target}`,
          {
            encoding: "utf8",
          }
        );
        console.log(
          JSON.stringify(
            { ok: true, status: 200, data: { killed: target } },
            null,
            2
          )
        );
      } catch (err) {
        console.error(
          JSON.stringify({ ok: false, error: String(err) }, null, 2)
        );
        process.exit(1);
      }
      return;
    }

    // ── Polling-based task manager (IndyDevDan pattern) ───────────────────
    case "poll-tasks":
      return call("/control/task-manager/poll", "POST", {
        source: args.source || "local", // local, linear, jira, github
        project: args.project || "",
        status_filter: args.status || "todo",
        max_tasks: args.max ? Number(args.max) : 5,
        agent: args.agent || "codex",
      });
    case "task-complete":
      return call("/control/task-manager/complete", "POST", {
        task_id: args.id || args["task-id"] || "",
        source: args.source || "local",
        result: args.result || "completed",
        evidence: args.evidence || "",
      });
    case "task-create":
      return call("/control/task-manager/create", "POST", {
        title: args.title || "",
        description: args.description || args.desc || "",
        source: args.source || "local",
        priority: args.priority || "normal",
        assignee: args.assignee || args.agent || "codex",
      });

    // ── Agent-to-Agent review handoff (IndyDevDan pattern) ────────────────
    case "review-handoff":
      return call("/control/review/agent-handoff", "POST", {
        from_agent: args.from || args["from-agent"] || "codex",
        to_agent: args.to || args["to-agent"] || "qwen",
        session_id: args.session || args.id || "",
        artifact_type: args.type || "code", // code, config, docs, test
        artifact_path: args.path || "",
        review_criteria: csv(args.criteria) || [
          "correctness",
          "style",
          "security",
        ],
        auto_merge:
          args["auto-merge"] === "true" || args["auto-merge"] === true,
      });
    case "review-status":
      return call(
        `/control/review/status?session_id=${encodeURIComponent(
          args.session || args.id || ""
        )}`,
        "GET"
      );
    case "review-accept":
      return call("/control/review/accept", "POST", {
        session_id: args.session || args.id || "",
        reviewer_agent: args.agent || "codex",
        reason: args.reason || "approved",
        evidence: args.evidence || "",
      });
    case "review-reject":
      return call("/control/review/reject", "POST", {
        session_id: args.session || args.id || "",
        reviewer_agent: args.agent || "codex",
        reason: args.reason || "",
        feedback: args.feedback || "",
        suggested_fixes: csv(args.fixes) || [],
      });

    // =========================================================================
    // Minor IndyDevDan Patterns - Evidence, Safety, Message Bus, Capability
    // =========================================================================

    // Evidence Capture API
    case "evidence-record":
      return call("/control/evidence/record", "POST", {
        session_id: args.session || args.id || "",
        task_id: args.task || "",
        agent_id: args.agent || "",
        type: args.type || "general",
        content: args.content ? JSON.parse(args.content) : {},
        command: args.command || "",
        output: args.output || "",
        exit_code: args["exit-code"] ? parseInt(args["exit-code"], 10) : null,
        files_changed: csv(args.files),
        tags: csv(args.tags),
      });

    case "evidence-list": {
      let url = `/control/evidence/list?session_id=${encodeURIComponent(
        args.session || args.id || ""
      )}`;
      if (args.type) url += `&type=${encodeURIComponent(args.type)}`;
      if (args.task) url += `&task_id=${encodeURIComponent(args.task)}`;
      return call(url, "GET");
    }

    // Safety Gate Pre-Hooks
    case "safety-check":
      return call("/control/safety/check", "POST", {
        command: args.command || "",
        operation: args.operation || "",
        context: args.context ? JSON.parse(args.context) : {},
      });

    case "safety-register-hook":
      return call("/control/safety/register-hook", "POST", {
        pattern: args.pattern || "",
        action: args.action || "warn",
        reason: args.reason || "Custom safety rule",
      });

    // Inter-Agent Message Bus
    case "bus-publish":
      return call("/control/message-bus/publish", "POST", {
        topic: args.topic || "",
        from_agent: args.agent || args.from || "",
        payload: args.payload ? JSON.parse(args.payload) : {},
        type: args.type || "info",
        correlation_id: args.correlation || "",
      });

    case "bus-subscribe":
      return call("/control/message-bus/subscribe", "POST", {
        topic: args.topic || "",
        agent_id: args.agent || "",
      });

    case "bus-poll": {
      let url = `/control/message-bus/poll?topic=${encodeURIComponent(
        args.topic || ""
      )}`;
      if (args.agent) url += `&agent_id=${encodeURIComponent(args.agent)}`;
      if (args.since) url += `&since=${encodeURIComponent(args.since)}`;
      if (args.limit) url += `&limit=${encodeURIComponent(args.limit)}`;
      return call(url, "GET");
    }

    // Historical Capability Scoring
    case "capability-record":
      return call("/control/capability/record-outcome", "POST", {
        agent_id: args.agent || "",
        capability: args.capability || "",
        task_id: args.task || "",
        success: args.success !== "false",
        quality_score: args.quality ? parseFloat(args.quality) : 1.0,
        duration_seconds: args.duration ? parseFloat(args.duration) : null,
        error_type: args.error || null,
        notes: args.notes || "",
      });

    case "capability-score": {
      let url = `/control/capability/score?agent_id=${encodeURIComponent(
        args.agent || ""
      )}`;
      if (args.capability)
        url += `&capability=${encodeURIComponent(args.capability)}`;
      if (args.window)
        url += `&window_hours=${encodeURIComponent(args.window)}`;
      return call(url, "GET");
    }

    // Rollback Execution API
    case "rollback-register":
      return call("/control/rollback/register", "POST", {
        session_id: args.session || args.id || "",
        task_id: args.task || "",
        commands: csv(args.commands),
        files: args.files ? JSON.parse(args.files) : {},
        description: args.description || "",
        agent_id: args.agent || "",
      });

    case "rollback-execute":
      return call("/control/rollback/execute", "POST", {
        session_id: args.session || args.id || "",
        dry_run: args["dry-run"] !== "false",
      });

    case "rollback-status":
      return call(
        `/control/rollback/status?session_id=${encodeURIComponent(
          args.session || args.id || ""
        )}`,
        "GET"
      );

    default:
      console.error(`Unknown command: ${cmd}`);
      process.exit(2);
  }
}

main().catch((err) => {
  console.error(JSON.stringify({ ok: false, error: String(err) }, null, 2));
  process.exit(1);
});
