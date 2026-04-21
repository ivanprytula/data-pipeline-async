# Pillar 6: AI / LLM Integration

**Tier**: Middle (🟡) → Senior (🔴)
**Project**: The 2025-2030 multiplier
**Building in**: `app/integrations/openai.py`, `app/routers/analyze.py`

---

## Middle Tier (🟡)

### LLM API Usage

**OpenAI SDK**:

```python
import openai

async def classify_record(record_data: dict) -> str:
    """Ask LLM to classify record."""
    response = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a data classifier. Return only the category."
            },
            {
                "role": "user",
                "content": f"Classify this: {record_data}"
            }
        ],
        temperature=0,  # Deterministic
    )
    return response.choices[0].message.content
```

**Error handling**:

```python
from openai import RateLimitError, APIError

async def classify_with_retry(record: dict) -> str:
    try:
        return await classify_record(record)
    except RateLimitError:
        await asyncio.sleep(2)  # Wait and retry
        return await classify_record(record)
    except APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return "ERROR"
```

**Structured output** (enforce schema):

```python
from pydantic import BaseModel

class Classification(BaseModel):
    category: str
    confidence: float
    explanation: str

response = await openai.ChatCompletion.acreate(
    model="gpt-4o",
    response_format={"type": "json_schema", "schema": Classification.model_json_schema()},
    messages=[...],
)
result = Classification.model_validate_json(response.choices[0].message.content)
```

---

### RAG Pipeline (Retrieval-Augmented Generation)

**Components**:

1. **Embeddings**: Convert text → vector
2. **Vector store**: Store + search vectors
3. **Retrieval**: Find relevant context
4. **Generation**: Feed context to LLM

**Example** (using `pgvector`):

```python
from openai import OpenAI

client = OpenAI()

async def embed_text(text: str) -> list[float]:
    """Get embedding for text."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding

async def store_embedding(db: AsyncSession, text: str, source: str):
    """Embed and store in pgvector."""
    embedding = await embed_text(text)
    obj = EmbeddingRecord(content=text, embedding=embedding, source=source)
    db.add(obj)
    await db.commit()

async def search_similar(db: AsyncSession, query: str, limit: int = 5) -> list[str]:
    """Find similar embeddings (cosine distance)."""
    query_embedding = await embed_text(query)

    # PostgreSQL pgvector: find nearest neighbors
    stmt = (
        select(EmbeddingRecord.content)
        .order_by(EmbeddingRecord.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    return await db.scalars(stmt).all()

async def rag_answer(db: AsyncSession, question: str) -> str:
    """RAG: retrieve context, then generate answer."""
    context = await search_similar(db, question, limit=3)
    context_str = "\n".join(context)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"Answer based on this context:\n{context_str}",
            },
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content
```

---

### GenAI Tool Proficiency

**GitHub Copilot**: Use for code generation, test scaffolding
**Claude**: Architecture review, complex refactoring
**Cursor / Windsurf**: Multi-file editing across codebase

---

## Senior (🔴)

### Agent Frameworks

**LangGraph** (stateful agents with conditional edges):

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class AgentState(TypedDict):
    records: list[dict]
    analysis: str
    action: str | None

def analyze_action(state: AgentState) -> AgentState:
    # Analyze records, decide next action
    state["action"] = "classify" if len(state["records"]) > 10 else "review"
    return state

def classify_node(state: AgentState) -> AgentState:
    # LLM classifies records
    for record in state["records"]:
        record["category"] = classify_openai(record)
    state["analysis"] = "Classification complete"
    return state

def review_node(state: AgentState) -> AgentState:
    state["analysis"] = "Manual review needed"
    return state

# Build graph
graph = StateGraph(AgentState)
graph.add_node("analyze", analyze_action)
graph.add_node("classify", classify_node)
graph.add_node("review", review_node)

graph.add_edge(START, "analyze")
graph.add_conditional_edges(
    "analyze",
    lambda state: "classify" if state["action"] == "classify" else "review",
)
graph.add_edge("classify", END)
graph.add_edge("review", END)

agent = graph.compile()
result = agent.invoke({"records": [...], "analysis": "", "action": None})
```

---

### MCP (Model Context Protocol)

Build custom MCP server that exposes your API to Claude Desktop:

```python
# mcp_server.py
from mcp.server import Server
from mcp.types import Tool

server = Server("data-pipeline-server")

@server.call_tool()
async def get_records(limit: int = 10) -> str:
    """Fetch records from API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8000/api/v1/records?limit={limit}")
    return response.text
```

Then in Claude Desktop, add:

```json
{
  "mcpServers": {
    "data-pipeline": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}
```

Claude can now call `get_records()` directly in chat

---

### Evaluation Pipelines

Use `ragas` to measure RAG quality:

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy

# Evaluate generated answers
results = evaluate(
    dataset=test_dataset,  # questions + ground truth answers
    metrics=[faithfulness, answer_relevancy]
)

print(f"Faithfulness: {results['faithfulness']}")  # Was answer factually correct?
print(f"Relevancy: {results['answer_relevancy']}")  # Did answer address question?
```

---

## You Should Be Able To

✅ Call OpenAI API and handle rate limits
✅ Embed text using embeddings API
✅ Build RAG pipeline: embed → store → retrieve → generate
✅ Use `pgvector` for similarity search
✅ Build stateful agent with `LangGraph`
✅ Create custom MCP server for Claude integration
✅ Measure RAG quality with evaluation metrics
✅ Explain why "jailbreak" prompts matter for security

---

## References

- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [LangChain](https://langchain.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [pgvector](https://github.com/pgvector/pgvector)
- [MCP Spec](https://modelcontextprotocol.io/)
- [RAGAS](https://ragas.io/)

---

## Checklist — Pillar 6: AI/LLM

### Foundation 🟢

- [ ] Call OpenAI chat completions API: system/user/assistant message roles
  - [ ] Know the difference between `temperature=0` (deterministic) and `temperature=1`
- [ ] Use `response_format` with a Pydantic model for structured output
- [ ] Explain what a token is and why context window limits matter
- [ ] Know what prompt injection is and why it's a security risk

### Middle 🟡

- [ ] Implement a RAG pipeline: chunk → embed → store in vector DB → retrieve → augment prompt
  - [ ] Know cosine similarity measures angle between vectors (direction, not magnitude)
  - [ ] Know HNSW index vs IVF-Flat: HNSW = approximate NN, better recall; IVF = partitioning
- [ ] Use LangChain LCEL: `prompt | llm | parser` chaining
- [ ] Choose an embedding model: OpenAI `text-embedding-3-small` vs `sentence-transformers`
  - [ ] Know: `3-small` = API call + cost; `sentence-transformers` = local + free
- [ ] Explain hallucination and three mitigation strategies

### Senior 🔴

- [ ] Explain fine-tuning vs RAG vs prompt engineering — when to use each
  - [ ] RAG = dynamic retrieval; fine-tuning = baked-in static knowledge; prompting = zero infra
- [ ] Design a LangGraph stateful agent with conditional routing
- [ ] Evaluate RAG quality with RAGAS metrics: faithfulness, answer relevance, context recall
- [ ] Identify production LLM concerns: cost per token, rate limits, latency, content policy
- [ ] Explain MCP (Model Context Protocol): tools, resources, prompt primitives

### Pre-Interview Refresh ✏️

- [ ] What is RAG and why is it better than fine-tuning for frequently changing data?
- [ ] What is hallucination? Name three mitigation strategies
- [ ] Explain the embed-store-retrieve cycle in three sentences
- [ ] When would you choose `text-embedding-3-small` over `3-large`?
- [ ] What is the difference between `temperature=0` and `temperature=1`?
