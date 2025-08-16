from multiprocessing import parent_process
from pathlib import Path
import os
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
import pandas as pd
from typing_extensions import Annotated, TypedDict
from typing import Dict, Any
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from pprint import pprint
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
import ast
import warnings
from sqlalchemy.exc import SAWarning
import json
warnings.filterwarnings("ignore", category=SAWarning)

class Database:
    """Manages the Chinook SQLite database file by using SQLAlchemy engine."""
    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)
        self.db_path: Path | None = None

    def choose_database(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        db_files = list(self.data_dir.glob("*.sqlite")) + list(self.data_dir.glob("*.db"))

        if not db_files:
            raise FileNotFoundError(f"No database files found in {self.data_dir}")

        # If only one DB, pick automatically
        if len(db_files) == 1:
            self.db_path = db_files[0]
            print(f"Using database: {self.db_path}")
            return

        print("Available databases:")
        for i, db_file in enumerate(db_files, 1):
            print(f"{i}. {db_file.name}")

        while True:
            choice = input(f"Select a database [1-{len(db_files)}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(db_files):
                self.db_path = db_files[int(choice) - 1]
                print(f"Using database: {self.db_path}")
                break
            else:
                print("Invalid choice. Try again.")

    def create_engine(self) -> Engine:
        self.choose_database()
        return create_engine(f"sqlite:///{self.db_path}")

    def create_sql_database(self) -> SQLDatabase:
        engine = self.create_engine()
        return SQLDatabase(engine)
    
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

class SQLAssistApp:
    def __init__(
        self,
        database: SQLDatabase,
        model_name: str = "gemini-2.0-flash-lite",
        model_provider="google_genai",
        top_k: int = 5,
        dialect: str = "SQLite",    
    ) -> None:
        load_dotenv()
        os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
        google_api_key = os.getenv("GOOGLE_API_KEY")
        
        self.dialect = dialect
        self.top_k = top_k
        self.database = database
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=google_api_key,
            temperature=0.1
        )
    
    def write_query(self, state: State) -> Dict[str, str]:
        system_message = """You are a SQL assistant. Generate a syntactically correct {dialect} query to answer the user's question.
             Unless the user specifies in his question a specific number of examples they wish to obtain, 
             always limit your query to at most {top_k} results. You can order the results by a relevant column to
             return the most interesting examples in the database.
             Never query for all the columns from a specific table, only ask for a the few relevant columns given the question.
             Pay attention to use only the column names that you can see in the schema
             description. Be careful to not query for columns that do not exist. Also,
             pay attention to which column is in which table.
             Only use the following tables: {table_info}"""
        query_prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", "{user_prompt}")
        ])
        prompt = query_prompt_template.invoke({
            "dialect": self.dialect,
            "top_k": self.top_k,
            "table_info": self.database.get_table_info(),
            "user_prompt": state["question"] or "",
        })
        structured_llm = self.llm.with_structured_output(QueryOutput)
        result = structured_llm.invoke(prompt)
        return {"query": result["query"]}
    
    def execute_query(self, state: State):
        execute_query_tool = QuerySQLDatabaseTool(db=self.database)
        raw_result = execute_query_tool.invoke(state["query"])
        
        if not raw_result:
            return {"result": pd.DataFrame()}
        
        try:
            result_list = ast.literal_eval(raw_result)
        except Exception:
            result_list = [raw_result]
                
        if result_list and (isinstance(result_list[0], (tuple, list)) or isinstance(result_list[0], dict)):
            result_df = pd.DataFrame(result_list)
        else:
            result_df = pd.DataFrame(result_list, columns=["value"])
        return {"result": result_df }
     
    def generate_answer(self, state: State):
        prompt = (
        "Given the following user question, corresponding SQL query, "
        "and SQL result, answer the user question if possible be insightful\n\n"
        f"Question: {state['question']}\n"
        f"SQL Query: {state['query']}\n"
        f"SQL Result: {state['result']}")
        response = self.llm.invoke(prompt)
        return {"answer": response.content}
    
    def validate_result(self, state: State):
        validation_prompt = f"""
You are an SQL validation assistant.

A user asked a natural language question and a SQL query was generated.
Your task is to check if the SQL query can reasonably answer the user's question. 

User question: "{state['question']}"
Generated SQL query: "{state['query']}"

Please answer in plain English:
- If the query is correct or mostly correct, say: "yes"
- If the query is incorrect, clearly irrelevant, or meaningless, say: "no"
- Consider that partial correctness is acceptable if the query returns relevant information

Do not generate SQL or execute anything, just validate the query.
"""
        is_valid = False
        validation_result = self.llm.invoke(validation_prompt)
        if "yes" in validation_result.content.lower():
            is_valid = True
            
        if not is_valid:
            state["query"] = None
            state["result"] = pd.DataFrame()
            state["answer"] = f"The SQL query could not be validated for your question. Please ask a clearer question.\n"
        return
        
    
    def query_structured(self, user_prompt: str) -> QueryResult:
        state: State = {
            "question": user_prompt,
            "query": None,
            "result": None,
            "answer": None,
            "row_count": None
        }
        
        query_result = self.write_query(state)
        state["query"] = query_result["query"]
        
        exec_result = self.execute_query(state)
        state["result"] = exec_result["result"]
        
        generate_answer = self.generate_answer(state)
        state["answer"] = generate_answer["answer"]
        
        self.validate_result(state)
        
        return QueryResult(
            question=state["question"],
            sql_query=state["query"],
            result=state["result"] if state["result"] is not None else pd.DataFrame(),
            answer=str(state["answer"]) if state["answer"] is not None else "",
            row_count=len(state["result"]) if state["result"] is not None else 0)
        
def display_results(result):
    print("\n" + "="*60)
    print(f"Question: {result['question']}")
    print("="*60)
    
    if result['sql_query'] is not None:
        print(f"\nGenerated SQL Query:")
        print("-" * 60)
        pprint(result['sql_query'])
        print(f"\nQuery Results:")
        display_table(result['result'])
        print(f"{result['row_count']} rows")
        print("-" * 60)
    else:
        print(f"\n")
    print(f"\nAI Answer:")
    print("-" * 60)
    print(result['answer'])
    

def display_table(df: pd.DataFrame) -> None:
    if df.empty:
        print("No results returned")
        return
    print(df.to_string(index=False, max_cols=10, max_colwidth=30))


chinook_test_questions = [
        "Who are the top 3 best selling artists?",
        "What are the 5 most popular music genres?",
        "Which customer have spent the most money? (give names)",
        "Show me the longest tracks in the database",
        "What are the total sales by country?"
    ]

sakila_test_questions = [
        "Which films have the highest rental rates?",
        "Show the 10 most recently added films",
        "What are the total payments received by store?",
        "List all films in the 'Action' category",
        "Which customers have not rented any films?"
]
general_test_questions = ["how many tables are in this database? "]

def main() -> None:
    db = Database()
    sql_database = db.create_sql_database()
    
    app = SQLAssistApp(sql_database)
    print("===== Natural Language to SQL Assistant =====")
    name_db = db.db_path.name.lower()
    print(f"Ask questions about the '{name_db}' database!")
    user_prompt = input("Type 'test' to see example queries or Enter your question: ")
    if user_prompt.lower() == 'test':
        if db.db_path and "chinook" in name_db:
            test_questions = chinook_test_questions
        elif db.db_path and "sakila" in name_db:
            test_questions = sakila_test_questions
        else:
            test_questions = general_test_questions
        for q in test_questions:
            result = app.query_structured(q)
            display_results(result)
    elif len(user_prompt) < 10:
        print(f"**The SQL query could not be validated for your question. Please ask a clearer question.**\n")
    else:
        result = app.query_structured(user_prompt)
        display_results(result)
    

if __name__ == "__main__":
    main()
