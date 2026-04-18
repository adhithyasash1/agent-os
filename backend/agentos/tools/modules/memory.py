import asyncio

from ..core import tool

@tool(
    name="search_memory",
    description="Search the agent's persistent memory. Supports both semantic search and Knowledge Graph traversal.",
    args_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search term for semantic retrieval"},
            "entity_id": {"type": "string", "description": "Optional entity ID to traverse the Knowledge Graph neighborhood"},
            "k": {"type": "integer", "description": "Number of results to fetch"}
        }
    },
    profiles=["full"]
)
async def _search_memory(args: dict, ctx: dict) -> dict:
    query = (args or {}).get("query", "").strip()
    entity_id = (args or {}).get("entity_id")
    k = (args or {}).get("k", 5)
    
    memory_store = ctx.get("memory")
    if not memory_store:
        return {"status": "error", "error": "No memory store injected."}
        
    try:
        results = {}
        
        # 1. Knowledge Graph Neighborhood
        if entity_id:
            results["graph"] = await asyncio.to_thread(memory_store.graph_search, entity_id)
            
        # 2. Semantic Search
        if query:
            search_hits = await asyncio.to_thread(memory_store.search, query, k)
            results["semantic"] = [
                {
                    "content": hit["text"],
                    "kind": hit["kind"],
                    "salience": hit.get("salience", 0.0)
                } for hit in search_hits
            ]
            
        if not results:
            return {"status": "error", "error": "Provide either query or entity_id."}
            
        return {"status": "ok", "output": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(
    name="save_knowledge",
    description="Save facts or complex relations to long-term memory. Follows the 2026 Golden Rule: the tool handles deduplication and cross-referencing.",
    args_schema={
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["name"]
                }
            },
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Name of the starting entity"},
                        "predicate": {"type": "string", "description": "Relation type (e.g. 'works_at', 'depends_on')"},
                        "object": {"type": "string", "description": "Name of the target entity"}
                    },
                    "required": ["subject", "predicate", "object"]
                }
            },
            "facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "General text observations to store semantically"
            }
        }
    },
    profiles=["full"]
)
async def _save_knowledge(args: dict, ctx: dict) -> dict:
    entities_data = (args or {}).get("entities", [])
    relations_data = (args or {}).get("relations", [])
    facts = (args or {}).get("facts", [])
    
    memory_store = ctx.get("memory")
    if not memory_store:
        return {"status": "error", "error": "No memory store injected."}
        
    try:
        summary = {"entities_saved": 0, "relations_linked": 0, "facts_indexed": 0}
        
        # 1. Save Entities
        name_to_id = {}
        for ent in entities_data:
            eid = await asyncio.to_thread(
                memory_store.upsert_entity,
                name=ent["name"],
                entity_type=ent.get("type"),
                description=ent.get("description")
            )
            name_to_id[ent["name"].lower()] = eid
            summary["entities_saved"] += 1
            
        # 2. Save Relations
        for rel in relations_data:
            # Ensure entities exist first (auto-creation of missing nodes)
            sub_id = name_to_id.get(rel["subject"].lower()) or await asyncio.to_thread(
                memory_store.upsert_entity,
                name=rel["subject"],
            )
            obj_id = name_to_id.get(rel["object"].lower()) or await asyncio.to_thread(
                memory_store.upsert_entity,
                name=rel["object"],
            )
            
            await asyncio.to_thread(memory_store.add_relation, sub_id, rel["predicate"], obj_id)
            summary["relations_linked"] += 1
            
        # 3. Save Plain Facts
        for fact in facts:
            await asyncio.to_thread(memory_store.add, fact, kind="semantic", salience=0.8)
            summary["facts_indexed"] += 1
            
        return {"status": "ok", "output": summary}
    except Exception as e:
        return {"status": "error", "error": str(e)}
