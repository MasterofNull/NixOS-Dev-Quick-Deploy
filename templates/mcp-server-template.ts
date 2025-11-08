/**
 * MCP Server Template (TypeScript/Deno)
 *
 * This template provides a starting point for building MCP servers
 * as described in https://www.anthropic.com/engineering/code-execution-with-mcp
 *
 * Key Features:
 * - Progressive tool discovery via filesystem navigation
 * - Data filtering in execution environment
 * - Secure sandboxing with bubblewrap/firejail
 * - State management through filesystem
 * - Token optimization (on-demand loading)
 */

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { walk } from "https://deno.land/std@0.208.0/fs/walk.ts";

// ============================================================================
// Configuration
// ============================================================================

const CONFIG = {
  port: parseInt(Deno.env.get("MCP_SERVER_PORT") || "8000"),
  toolsDir: Deno.env.get("MCP_TOOLS_DIR") || "./servers",
  stateDir: Deno.env.get("MCP_STATE_DIR") || "./state",
  enableSandbox: Deno.env.get("MCP_ENABLE_SANDBOX") === "true",
  databases: {
    postgresql: {
      host: Deno.env.get("POSTGRES_HOST") || "127.0.0.1",
      port: parseInt(Deno.env.get("POSTGRES_PORT") || "5432"),
      database: Deno.env.get("POSTGRES_DB") || "mcp",
      user: Deno.env.get("POSTGRES_USER") || "mcp",
    },
    redis: {
      host: Deno.env.get("REDIS_HOST") || "127.0.0.1",
      port: parseInt(Deno.env.get("REDIS_PORT") || "6379"),
      password: Deno.env.get("REDIS_PASSWORD") || "mcp-dev-password-change-in-production",
    },
    qdrant: {
      host: Deno.env.get("QDRANT_HOST") || "127.0.0.1",
      port: parseInt(Deno.env.get("QDRANT_PORT") || "6333"),
    },
  },
};

// ============================================================================
// Types
// ============================================================================

interface ToolDefinition {
  name: string;
  description: string;
  path: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
}

interface MCPRequest {
  action: "list_tools" | "search_tools" | "execute" | "get_tool";
  params?: {
    query?: string;
    detail_level?: "minimal" | "full";
    tool_name?: string;
    input?: Record<string, unknown>;
  };
}

interface MCPResponse {
  success: boolean;
  data?: unknown;
  error?: string;
}

// ============================================================================
// Tool Discovery (Progressive Disclosure)
// ============================================================================

async function discoverTools(
  detailLevel: "minimal" | "full" = "minimal"
): Promise<ToolDefinition[]> {
  const tools: ToolDefinition[] = [];

  for await (const entry of walk(CONFIG.toolsDir, {
    exts: [".ts", ".js"],
    skip: [/node_modules/, /\.test\./],
  })) {
    if (entry.isFile) {
      const relativePath = entry.path.replace(CONFIG.toolsDir + "/", "");
      const toolName = relativePath.replace(/\.(ts|js)$/, "").replace(/\//g, ".");

      if (detailLevel === "minimal") {
        // Only return tool names for token efficiency
        tools.push({
          name: toolName,
          description: "",
          path: entry.path,
        });
      } else {
        // Load full tool definition
        const definition = await loadToolDefinition(entry.path);
        tools.push({
          name: toolName,
          description: definition.description || "",
          path: entry.path,
          input: definition.input,
          output: definition.output,
        });
      }
    }
  }

  return tools;
}

async function searchTools(
  query: string,
  detailLevel: "minimal" | "full" = "minimal"
): Promise<ToolDefinition[]> {
  const allTools = await discoverTools(detailLevel);

  // Simple fuzzy search - can be enhanced with vector embeddings via Qdrant
  return allTools.filter(tool =>
    tool.name.toLowerCase().includes(query.toLowerCase()) ||
    tool.description?.toLowerCase().includes(query.toLowerCase())
  );
}

async function loadToolDefinition(path: string): Promise<ToolDefinition> {
  try {
    // Dynamic import of tool module
    const module = await import(`file://${path}`);
    return {
      name: module.name || "",
      description: module.description || "",
      path,
      input: module.input,
      output: module.output,
    };
  } catch (error) {
    console.error(`Failed to load tool from ${path}:`, error);
    return {
      name: "",
      description: "",
      path,
    };
  }
}

// ============================================================================
// Code Execution (Sandboxed)
// ============================================================================

async function executeCode(
  code: string,
  sandbox = CONFIG.enableSandbox
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const tempFile = await Deno.makeTempFile({ suffix: ".ts" });

  try {
    // Write code to temporary file
    await Deno.writeTextFile(tempFile, code);

    let command: string[];

    if (sandbox) {
      // Execute with bubblewrap sandboxing
      command = [
        "bwrap",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
        "--tmpfs", "/tmp",
        "--proc", "/proc",
        "--dev", "/dev",
        "--unshare-all",
        "--share-net",
        "--die-with-parent",
        "deno", "run", "--allow-net", "--allow-read", tempFile,
      ];
    } else {
      command = ["deno", "run", "--allow-net", "--allow-read", tempFile];
    }

    const process = Deno.run({
      cmd: command,
      stdout: "piped",
      stderr: "piped",
    });

    const [status, stdout, stderr] = await Promise.all([
      process.status(),
      process.output(),
      process.stderrOutput(),
    ]);

    process.close();

    return {
      stdout: new TextDecoder().decode(stdout),
      stderr: new TextDecoder().decode(stderr),
      exitCode: status.code,
    };
  } finally {
    // Clean up temp file
    try {
      await Deno.remove(tempFile);
    } catch {
      // Ignore cleanup errors
    }
  }
}

// ============================================================================
// Data Filtering (Pre-processing before returning to model)
// ============================================================================

function filterLargeDataset(
  data: unknown[],
  filter: (item: unknown) => boolean,
  maxRows = 100
): unknown[] {
  // Filter data in execution environment to reduce tokens
  // Example: 10,000 rows -> only relevant rows returned to model
  return data.filter(filter).slice(0, maxRows);
}

// ============================================================================
// State Management
// ============================================================================

async function saveState(key: string, value: unknown): Promise<void> {
  const statePath = `${CONFIG.stateDir}/${key}.json`;
  await Deno.mkdir(CONFIG.stateDir, { recursive: true });
  await Deno.writeTextFile(statePath, JSON.stringify(value, null, 2));
}

async function loadState<T>(key: string): Promise<T | null> {
  try {
    const statePath = `${CONFIG.stateDir}/${key}.json`;
    const content = await Deno.readTextFile(statePath);
    return JSON.parse(content);
  } catch {
    return null;
  }
}

// ============================================================================
// HTTP Server
// ============================================================================

async function handleRequest(request: Request): Promise<Response> {
  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  try {
    const mcpRequest: MCPRequest = await request.json();
    let response: MCPResponse;

    switch (mcpRequest.action) {
      case "list_tools": {
        const tools = await discoverTools(
          mcpRequest.params?.detail_level || "minimal"
        );
        response = { success: true, data: tools };
        break;
      }

      case "search_tools": {
        if (!mcpRequest.params?.query) {
          response = { success: false, error: "Query parameter required" };
          break;
        }
        const tools = await searchTools(
          mcpRequest.params.query,
          mcpRequest.params.detail_level || "minimal"
        );
        response = { success: true, data: tools };
        break;
      }

      case "get_tool": {
        if (!mcpRequest.params?.tool_name) {
          response = { success: false, error: "Tool name required" };
          break;
        }
        // Load full definition for specific tool
        const tools = await discoverTools("full");
        const tool = tools.find(t => t.name === mcpRequest.params?.tool_name);
        response = tool
          ? { success: true, data: tool }
          : { success: false, error: "Tool not found" };
        break;
      }

      case "execute": {
        // This would integrate with the actual tool execution
        response = { success: false, error: "Not implemented yet" };
        break;
      }

      default:
        response = { success: false, error: "Unknown action" };
    }

    return new Response(JSON.stringify(response), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    return new Response(
      JSON.stringify({ success: false, error: String(error) }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}

// ============================================================================
// Main
// ============================================================================

console.log(`MCP Server starting on port ${CONFIG.port}...`);
console.log(`Tools directory: ${CONFIG.toolsDir}`);
console.log(`State directory: ${CONFIG.stateDir}`);
console.log(`Sandbox enabled: ${CONFIG.enableSandbox}`);

await serve(handleRequest, { port: CONFIG.port });
