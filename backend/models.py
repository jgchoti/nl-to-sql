from typing_extensions import TypedDict
import pandas as pd

class QueryOutput(TypedDict):
    """Generated SQL query."""
    query: str
    
class State(TypedDict):
    question: str
    query: str | None
    result: str | None
    answer: str | None
    row_count: int | None
    
class QueryResult(TypedDict):
    question: str
    sql_query: str
    result: pd.DataFrame
    answer: str
    row_count: int