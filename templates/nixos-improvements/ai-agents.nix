# AI Agent Stack Configuration
# Target: Local coding agents, RAG systems, agentic workflows
# Purpose: Token-efficient, high-performance AI agent infrastructure
#
# Features:
# - smolagents (Hugging Face lightweight agents)
# - LangGraph (stateful agent workflows)
# - CrewAI (multi-agent orchestration)
# - RAG optimization tools
# - MCP server integration
# - Token optimization strategies
#
# Usage: This module provides Python packages and configurations
# Import in home.nix via the Python environment
#
# December 2025 Best Practices Implemented:
# - Semantic chunking for RAG
# - Hybrid search (dense + sparse)
# - Reranking for relevance
# - Context compression
# - Tool calling optimization
# - Multi-agent coordination

{ config, pkgs, lib, ... }:

let
  # AI Agent Python packages
  # Note: These are installed via pip in the Python environment
  # as many cutting-edge packages aren't in nixpkgs yet
  
  aiAgentPipPackages = ''
    # ==========================================================================
    # Core Agent Frameworks (December 2025)
    # ==========================================================================
    
    # smolagents - Hugging Face lightweight agent framework
    # https://github.com/huggingface/smolagents
    # - Minimal token usage with code-based actions
    # - Direct tool execution without verbose prompting
    # - Built-in web search, code execution, image tools
    smolagents
    
    # LangGraph - Stateful agent workflows
    # - State machine for complex agent flows
    # - Checkpointing and resumption
    # - Human-in-the-loop support
    langgraph
    
    # CrewAI - Multi-agent orchestration
    # - Role-based agents (researcher, writer, coder)
    # - Task delegation and collaboration
    # - Memory and context sharing
    crewai
    crewai-tools
    
    # ==========================================================================
    # RAG Optimization (Token Efficiency)
    # ==========================================================================
    
    # Semantic Chunking
    # - Splits documents by meaning, not fixed size
    # - Preserves context boundaries
    # - Reduces redundant tokens
    semantic-text-splitter
    unstructured
    
    # Hybrid Search (Dense + Sparse)
    # - BM25 for keyword matching
    # - Dense vectors for semantic similarity
    # - Reciprocal Rank Fusion for combining
    rank-bm25
    
    # Reranking
    # - Cross-encoder reranking for relevance
    # - Reduces context window usage
    # - Improves answer quality
    flashrank
    
    # Context Compression
    # - LLMLingua-style compression
    # - Removes redundant tokens from context
    # - Up to 20x compression with minimal quality loss
    llmlingua
    
    # ==========================================================================
    # Tool Calling & Function Execution
    # ==========================================================================
    
    # Instructor - Structured outputs from LLMs
    # - Type-safe function calling
    # - Pydantic model validation
    # - Retry with error correction
    instructor
    
    # Outlines - Structured generation
    # - Grammar-constrained generation
    # - JSON schema enforcement
    # - Regex pattern matching
    outlines
    
    # ==========================================================================
    # Code Execution & Analysis
    # ==========================================================================
    
    # Code execution sandbox
    # - Safe code execution in containers
    # - Resource limits and timeouts
    # - Multi-language support
    e2b
    
    # AST analysis for code understanding
    # - Tree-sitter for fast parsing
    # - Language-agnostic code analysis
    tree-sitter
    
    # ==========================================================================
    # Memory & Context Management
    # ==========================================================================
    
    # Conversation memory
    # - Sliding window with summarization
    # - Entity extraction and tracking
    # - Long-term memory storage
    mem0ai
    
    # ==========================================================================
    # MCP (Model Context Protocol) Integration
    # ==========================================================================
    
    # MCP client for tool servers
    # - Standardized tool interface
    # - Server discovery and connection
    # - Resource management
    mcp
    
    # ==========================================================================
    # Monitoring & Observability
    # ==========================================================================
    
    # LangSmith/LangFuse for tracing
    # - Request/response logging
    # - Token usage tracking
    # - Latency monitoring
    langfuse
    
    # Phoenix for LLM observability
    # - Trace visualization
    # - Embedding analysis
    # - Hallucination detection
    arize-phoenix
  '';

  # Agent configuration best practices
  agentConfigBestPractices = ''
    # ==========================================================================
    # Token Optimization Best Practices (December 2025)
    # ==========================================================================
    
    1. PROMPT ENGINEERING
       - Use concise system prompts (< 500 tokens)
       - Prefer examples over verbose instructions
       - Use structured output formats (JSON, YAML)
       - Implement few-shot learning with minimal examples
    
    2. CONTEXT MANAGEMENT
       - Semantic chunking (512-1024 tokens per chunk)
       - Hybrid search (BM25 + dense vectors)
       - Reranking to select top-K most relevant
       - Context compression for large documents
       - Sliding window with summarization
    
    3. TOOL CALLING EFFICIENCY
       - Use structured outputs (Instructor, Outlines)
       - Batch tool calls when possible
       - Cache tool results for repeated queries
       - Implement tool result summarization
    
    4. MULTI-AGENT OPTIMIZATION
       - Specialized agents for specific tasks
       - Shared memory to avoid redundant queries
       - Hierarchical task delegation
       - Early termination when goal achieved
    
    5. RAG OPTIMIZATION
       - Query expansion for better retrieval
       - Document deduplication
       - Metadata filtering before vector search
       - Adaptive chunk sizes based on content type
    
    6. MODEL SELECTION
       - Small models for simple tasks (Qwen2.5-Coder-1.5B)
       - Medium models for reasoning (Qwen3-8B)
       - Large models only for complex tasks (Qwen3-32B)
       - Speculative decoding for speed
    
    7. CACHING STRATEGIES
       - Semantic cache for similar queries
       - Embedding cache for documents
       - Tool result cache with TTL
       - Prompt template caching
  '';

in
{
  # This module provides configuration documentation
  # The actual packages are installed via pip in the Python environment
  
  environment.etc."nixos/AI-AGENT-STACK.md".text = ''
    # AI Agent Stack Configuration
    
    ## Installed Agent Frameworks
    
    ### smolagents (Hugging Face)
    Lightweight agent framework optimized for token efficiency.
    
    ```python
    from smolagents import CodeAgent, ToolCallingAgent, HfApiModel
    
    # Use with local Ollama
    model = HfApiModel(model_id="http://localhost:11434/v1")
    
    # Code-based agent (most token efficient)
    agent = CodeAgent(tools=[], model=model)
    result = agent.run("Write a function to calculate fibonacci")
    ```
    
    ### LangGraph (Stateful Workflows)
    For complex multi-step agent workflows.
    
    ```python
    from langgraph.graph import StateGraph, MessagesState
    
    # Define workflow
    workflow = StateGraph(MessagesState)
    workflow.add_node("research", research_node)
    workflow.add_node("code", code_node)
    workflow.add_edge("research", "code")
    
    # Compile and run
    app = workflow.compile()
    result = app.invoke({"messages": [("user", "Build a REST API")]})
    ```
    
    ### CrewAI (Multi-Agent)
    For team-based agent orchestration.
    
    ```python
    from crewai import Agent, Task, Crew
    
    researcher = Agent(role="Researcher", goal="Find information")
    coder = Agent(role="Coder", goal="Write clean code")
    
    crew = Crew(agents=[researcher, coder], tasks=[...])
    result = crew.kickoff()
    ```
    
    ## RAG Optimization Tools
    
    ### Semantic Chunking
    ```python
    from semantic_text_splitter import TextSplitter
    
    splitter = TextSplitter(capacity=512)  # Token-based
    chunks = splitter.chunks(document)
    ```
    
    ### Hybrid Search
    ```python
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer
    
    # BM25 for keywords
    bm25 = BM25Okapi(tokenized_corpus)
    bm25_scores = bm25.get_scores(query_tokens)
    
    # Dense vectors for semantic
    model = SentenceTransformer("all-MiniLM-L6-v2")
    dense_scores = model.similarity(query_embedding, doc_embeddings)
    
    # Combine with RRF
    combined = reciprocal_rank_fusion([bm25_scores, dense_scores])
    ```
    
    ### Context Compression
    ```python
    from llmlingua import PromptCompressor
    
    compressor = PromptCompressor()
    compressed = compressor.compress_prompt(
        context=long_context,
        target_token=500,
        condition_in_question="How does X work?"
    )
    ```
    
    ## Token Usage Monitoring
    
    ```python
    from langfuse import Langfuse
    
    langfuse = Langfuse()
    
    @langfuse.trace()
    def my_agent_call(query):
        # Your agent code
        pass
    
    # View traces at http://localhost:3000
    ```
    
    ## Recommended Models for Mobile Workstation
    
    | Task | Model | Size | VRAM |
    |------|-------|------|------|
    | Code completion | Qwen2.5-Coder-1.5B | 1.5B | 2GB |
    | Code generation | Qwen2.5-Coder-7B | 7B | 6GB |
    | Reasoning | Qwen3-8B | 8B | 6GB |
    | Complex tasks | Qwen3-14B | 14B | 10GB |
    | Embeddings | nomic-embed-text | 137M | 1GB |
    
    ## MCP Server Integration
    
    ```bash
    # List available MCP servers
    mcp list-servers
    
    # Connect to filesystem server
    mcp connect filesystem --root ~/projects
    
    # Use in agent
    from mcp import ClientSession
    async with ClientSession() as session:
        result = await session.call_tool("read_file", {"path": "main.py"})
    ```
    
    ## Best Practices
    
    ${agentConfigBestPractices}
  '';
}

