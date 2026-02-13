# AIDB Indexing and Telemetry Schema Guarantees

## Schema Guarantees for Agent Integration

This document provides the guaranteed schemas for AIDB indexing and telemetry that agents can rely on for integration.

### AIDB Document Indexing Schema

#### Imported Documents Table Schema
```sql
Table: imported_documents
Columns:
- id: UUID (primary key)
- project: VARCHAR (project identifier)
- relative_path: VARCHAR (file path)
- title: VARCHAR (document title)
- content_type: VARCHAR (mime type)
- content: TEXT (document content)
- size_bytes: INTEGER (file size)
- imported_at: TIMESTAMP (import time)
- status: VARCHAR (approved/pending/rejected)
- metadata: JSONB (additional metadata)
```

#### Document Import API
```json
{
  "project": "string (required)",
  "relative_path": "string (required)",
  "title": "string (required)",
  "content_type": "string (required)",
  "content": "string (required)",
  "size_bytes": "integer (optional)",
  "metadata": "object (optional)"
}
```

#### Document Search Response Schema
```json
{
  "documents": [
    {
      "id": "uuid",
      "project": "string",
      "relative_path": "string", 
      "title": "string",
      "content_type": "string",
      "size_bytes": "integer",
      "imported_at": "ISO8601 timestamp",
      "status": "string",
      "content": "string (if included)"
    }
  ],
  "total": "integer",
  "project": "string"
}
```

### AIDB Vector Storage Schema

#### Embeddings Table Schema
```sql
Table: document_embeddings
Columns:
- id: UUID (primary key)
- document_id: UUID (foreign key to imported_documents)
- collection_name: VARCHAR (vector collection)
- embedding: vector (pgvector format)
- chunk_text: TEXT (chunked content)
- chunk_index: INTEGER (position in document)
- created_at: TIMESTAMP
- metadata: JSONB (additional metadata)
```

#### Vector Search Request Schema
```json
{
  "collection": "string (required)",
  "query": "string (required)",
  "limit": "integer (default 10)",
  "offset": "integer (default 0)", 
  "min_score": "float (default 0.0)",
  "filters": "object (optional)"
}
```

#### Vector Search Response Schema
```json
{
  "results": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "collection": "string",
      "content": "string",
      "score": "float",
      "metadata": "object",
      "distance": "float"
    }
  ],
  "total": "integer",
  "limit": "integer",
  "offset": "integer",
  "has_more": "boolean"
}
```

### AIDB Telemetry Schema

#### Telemetry Events Table Schema
```sql
Table: telemetry_events
Columns:
- id: UUID (primary key)
- source: VARCHAR (service name)
- event_type: VARCHAR (event type)
- llm_used: VARCHAR (local/remote)
- tokens_saved: INTEGER (estimated tokens saved)
- rag_hits: INTEGER (RAG hits)
- collections_used: TEXT[] (array of collection names)
- model: VARCHAR (model name)
- latency_ms: INTEGER (response time)
- cache_hit: BOOLEAN (was cached)
- metadata: JSONB (event metadata)
- created_at: TIMESTAMP
```

#### Telemetry Record Schema
```json
{
  "source": "string (required)",
  "event_type": "string (required)",
  "llm_used": "string (local|remote)",
  "tokens_saved": "integer",
  "rag_hits": "integer", 
  "collections_used": "array of strings",
  "model": "string",
  "latency_ms": "integer",
  "cache_hit": "boolean",
  "metadata": "object"
}
```

#### Telemetry Summary Response Schema
```json
{
  "total_events": "integer",
  "local_events": "integer", 
  "remote_events": "integer",
  "tokens_saved_total": "integer",
  "last_event_at": "ISO8601 timestamp",
  "telemetry_path": "string",
  "enabled": "boolean",
  "local_usage_rate": "float"
}
```

### AIDB Skills Schema

#### Skills Table Schema
```sql
Table: skills
Columns:
- id: UUID (primary key)
- name: VARCHAR (unique skill name)
- description: TEXT (skill description)
- category: VARCHAR (skill category)
- parameters: JSONB (parameter schema)
- implementation: TEXT (skill implementation)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
- enabled: BOOLEAN
```

#### Skill Registration Schema
```json
{
  "name": "string (required)",
  "description": "string (required)", 
  "category": "string (required)",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": "array of strings"
  },
  "implementation": "string (required)"
}
```

### AIDB Tools Schema

#### Tools Registry Schema
```json
{
  "name": "string (required)",
  "description": "string (required)",
  "parameters": {
    "type": "object",
    "properties": {
      "param_name": {
        "type": "string",
        "description": "string",
        "required": "boolean"
      }
    }
  },
  "function": "callable function reference"
}
```

### AIDB ML Models Schema

#### ML Models Table Schema
```sql
Table: ml_models
Columns:
- id: UUID (primary key)
- name: VARCHAR (unique name)
- model_type: VARCHAR (classification/regression/clustering)
- features: TEXT[] (feature names)
- model_artifact: BYTEA (serialized model)
- training_data_info: JSONB (training data metadata)
- performance_metrics: JSONB (accuracy, precision, etc.)
- status: VARCHAR (training/ready/failed)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

### AIDB Query Validation Schema

#### Vector Search Request Schema
```json
{
  "collection": "string (required)",
  "query": "string (required, max 10KB)",
  "limit": "integer (1-100)",
  "offset": "integer (>=0)", 
  "min_score": "float (0.0-1.0)"
}
```

#### Validated Response Schema
```json
{
  "results": "array of search results",
  "total": "integer",
  "limit": "integer", 
  "offset": "integer",
  "has_more": "boolean",
  "query_time_ms": "float"
}
```

### Schema Versioning and Compatibility

#### Version Guarantees
- **Schema Version 1.0**: Backward compatible for 12 months
- **Breaking Changes**: Announced 3 months in advance
- **New Fields**: Always backward compatible (optional)

#### Migration Strategy
- Database migrations handled automatically
- API versioning through query parameters
- Deprecation warnings before removal

### Agent Integration Guarantees

#### Minimum Guaranteed Schema Stability
- Core document fields: 24 months
- Telemetry event structure: 12 months  
- Search API: 18 months
- Authentication: 24 months

#### Required Agent Behaviors
1. Handle optional fields gracefully
2. Use default values for missing fields
3. Validate response schemas before processing
4. Implement retry logic for transient failures

#### Error Handling Guarantees
- Consistent error response format
- Standard HTTP status codes
- Descriptive error messages
- Structured error details

This provides the schema guarantees that agents can rely on for stable integration with AIDB.