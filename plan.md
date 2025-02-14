# Implementation Plan: Adding LLM Result Processing

## 1. Create New LLM Module (app/llm/result_processor.py)

Create a new module to handle result summarization with these key functions:

```python
@observe()
async def process_query_results(
    results: List[Dict[str, Any]], 
    question: str,
    sql: str,
    preview: Dict[str, Any]
) -> str:
    """
    Process query results using LLM to generate a concise, insightful summary.
    
    Args:
        results: The full query results
        question: Original user question
        sql: Generated SQL query
        preview: Preview data including column names and sample rows
        
    Returns:
        str: A concise summary (guaranteed < 1500 chars to allow for formatting)
    """
```

### System Prompt for Result Processing

```
You are an expert data analyst helping users understand query results. Given a user's question and the query results:

1. Provide a clear, concise answer (max 1500 characters)
2. Focus on insights relevant to the original question
3. Include key statistics or aggregates if relevant
4. Format numbers for readability
5. If the data has time series, note any trends
6. If results are empty, explain possible reasons why

Remember:
- Be concise but informative
- Highlight the most important findings
- Use natural language
- Stay under the character limit
```

## 2. Modify Query Router (app/routers/query.py)

### Update QueryResponse Schema

```python
class QueryResponse(BaseModel):
    answer: str  # LLM-processed summary
    generated_sql: str
    preview: Optional[TablePreview]  # Keep raw data preview
    raw_answer: Optional[str]  # Original count-based answer
```

### Update Query Handler

1. Keep existing SQL generation and safety checks
2. Execute query and create preview as before
3. Add new step to process results:
```python
# Process results with LLM
processed_answer = await process_query_results(
    results=results,
    question=req.question,
    sql=generated_sql,
    preview=preview.dict()
)

return QueryResponse(
    answer=processed_answer,
    raw_answer=basic_answer,  # Store original answer
    generated_sql=generated_sql,
    preview=preview
)
```

## 3. Update Discord Bot (discord_bot/bot.py)

### Message Structure

Format Discord messages as:

```
**Answer**: {processed_answer}

**Data Preview**:
(Only included if space permits after the main answer)
```

### Implementation Details

1. First send the processed answer:
```python
# Always send the processed answer first
await interaction.followup.send(
    f"**Answer**: {data['answer']}", 
    ephemeral=True
)
```

2. Then optionally send preview if space permits:
```python
# Calculate remaining space for preview
preview_msg = format_preview(data['preview'])
if len(preview_msg) <= 2000:
    await interaction.followup.send(
        f"**Data Preview**:\n{preview_msg}",
        ephemeral=True
    )
```

## Testing Strategy

1. Unit Tests
   - Test result processor with various data shapes
   - Verify character limit compliance
   - Check handling of empty results
   
2. Integration Tests
   - End-to-end flow from question to formatted answer
   - Different query types (aggregations, time series, etc.)
   - Error cases and fallbacks

## Implementation Steps

1. Set up test environment and write initial tests
2. Create result processor module
3. Update query router and schemas
4. Modify Discord bot
5. Manual testing with various queries
6. Deploy and monitor

With these detailed specifications, we can now switch to Code mode to implement the solution. The implementation should be straightforward since we have clearly defined the interfaces and behavior.