import asyncio
import os
import sys
from pathlib import Path

# Mock environment for settings loader
os.environ["AIDB_CONFIG"] = "/dev/null"
os.environ["AI_STRICT_ENV"] = "false"
os.environ["DATABASE_URL"] = "postgresql://aidb@127.0.0.1:5432/aidb"
os.environ["EMBEDDING_SERVICE_URL"] = "http://localhost:8081"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["LLAMA_CPP_BASE_URL"] = "http://localhost:8080"
os.environ["DATA_DIR"] = "/tmp/aidb-test"

# Add AIDB to path
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parents[2] / "mcp-servers"))

import sqlalchemy as sa
from interaction_history import InteractionHistoryStore
from settings_loader import load_settings

async def validate_history():
    print("🚀 Validating Interaction History Store...")
    
    # Securely retrieve password from system secrets
    secret_path = "/run/secrets/postgres_password"
    password = ""
    if os.path.exists(secret_path):
        with open(secret_path, 'r') as f:
            password = f.read().strip()
    
    import urllib.parse
    quoted_password = urllib.parse.quote_plus(password)
    dsn = f"postgresql://aidb:{quoted_password}@127.0.0.1:5432/aidb"
    engine = sa.create_engine(dsn)
    
    store = InteractionHistoryStore(engine)
    
    # Ensure table exists (in case it wasn't created yet)
    print("Ensuring interaction_history table exists...")
    from schema import INTERACTION_HISTORY
    try:
        with engine.begin() as conn:
            INTERACTION_HISTORY.create(conn, checkfirst=True)
    except Exception as e:
        print(f"Note: Table creation check: {e}")
    
    # 1. Record an interaction
    interaction = {
        "query": "Who is the owner of this project?",
        "response": "The owner is hyperd.",
        "agent_type": "gemini-cli-test",
        "outcome": "success",
        "tokens_in": 10,
        "tokens_out": 5,
        "latency_ms": 150,
        "project": "test-project",
        "metadata": {"test": True}
    }
    
    print("Recording interaction...")
    interaction_id = await store.record_interaction(interaction)
    print(f"✅ Recorded interaction ID: {interaction_id}")
    
    # 2. Retrieve history
    print("Retrieving history...")
    history = await store.get_history(agent_type="gemini-cli-test", limit=1)
    if history and history[0]['query'] == interaction['query']:
        print("✅ History retrieval successful")
    else:
        print("❌ History retrieval failed or mismatched")
        return False
        
    # 3. Get stats
    print("Getting stats...")
    stats = await store.get_stats()
    print(f"✅ Stats: {stats}")
    if stats['total_interactions'] > 0:
        print("✅ Stats check successful")
    else:
        print("❌ Stats check failed")
        return False
        
    print("🎉 All Interaction History validations passed!")
    return True

if __name__ == "__main__":
    # Ensure we are in the correct dir
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try:
        success = asyncio.run(validate_history())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        sys.exit(1)
