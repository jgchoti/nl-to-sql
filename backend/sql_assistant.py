import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langchain_community.utilities.sql_database import SQLDatabase
import pandas as pd
import ast
from typing import Dict
from models import QueryOutput, State, QueryResult

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
        
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        self.dialect = dialect
        self.top_k = top_k
        self.database = database
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=google_api_key,
            temperature=0.1
        )
    
    def write_query(self, state: State) -> Dict[str, str]:
        try:
            # Get actual table information
            table_info = self.database.get_table_info()
            print(f"Available tables: {table_info}")
            
            system_message = """You are a SQL assistant. Generate a syntactically correct {dialect} query to answer the user's question.
                 Unless the user specifies in his question a specific number of examples they wish to obtain, 
                 always limit your query to at most {top_k} results. You can order the results by a relevant column to
                 return the most interesting examples in the database.
                 Never query for all the columns from a specific table, only ask for a the few relevant columns given the question.
                 Pay attention to use only the column names that you can see in the schema
                 description. Be careful to not query for columns that do not exist. Also,
                 pay attention to which column is in which table.
                 
                 IMPORTANT: Only use the following tables and their exact names: {table_info}
                 
                 If the user asks for "first 5 rows" or similar, use the FIRST table name from the schema above.
                 Do NOT use placeholder names like 'your_table' - use the actual table names provided."""
                 
            query_prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("human", "{user_prompt}")
            ])
            
            prompt = query_prompt_template.invoke({
                "dialect": self.dialect,
                "top_k": self.top_k,
                "table_info": table_info,
                "user_prompt": state["question"] or "",
            })
            
            structured_llm = self.llm.with_structured_output(QueryOutput)
            result = structured_llm.invoke(prompt)
            
            generated_query = result.query if hasattr(result, 'query') else result["query"]
            print(f"Generated query: {generated_query}")
            
            return {"query": generated_query}
            
        except Exception as e:
            print(f"Error in write_query: {e}")
    
            try:
                table_info = self.database.get_table_info()

                lines = table_info.split('\n')
                first_table = None
                for line in lines:
                    if 'CREATE TABLE' in line:
                        parts = line.split()
                        if len(parts) > 2:
                            first_table = parts[2].strip('`"[]')
                            break
                
                if first_table:
                    fallback_query = f"SELECT * FROM {first_table} LIMIT 5;"
                else:
                    fallback_query = "SELECT name FROM sqlite_master WHERE type='table';"
                    
                print(f"Using fallback query: {fallback_query}")
                return {"query": fallback_query}
            except:
                return {"query": "SELECT name FROM sqlite_master WHERE type='table';"}
    
    def execute_query(self, state: State):
        try:
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
            return {"result": result_df}
        except Exception as e:
            print(f"Error in execute_query: {e}")
            return {"result": pd.DataFrame()}
     
    def generate_answer(self, state: State):
        try:
            prompt = (
            "Given the following user question, corresponding SQL query, "
            "and SQL result, answer the user question if possible be insightful\n\n"
            f"Question: {state['question']}\n"
            f"SQL Query: {state['query']}\n"
            f"SQL Result: {state['result']}")
            response = self.llm.invoke(prompt)
            return {"answer": response.content}
        except Exception as e:
            print(f"Error in generate_answer: {e}")
            return {"answer": f"Query executed successfully. Found {len(state.get('result', pd.DataFrame()))} results."}
    
    def validate_result(self, state: State):
        try:
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
        except Exception as e:
            print(f"Error in validate_result: {e}")
            pass
        
        return state
    
    def query_structured(self, user_prompt: str) -> QueryResult:
        """Main method that returns a QueryResult object"""
        state: State = {
            "question": user_prompt,
            "query": None,
            "result": None,
            "answer": None,
            "row_count": None
        }
        
        try:
            query_result = self.write_query(state)
            state["query"] = query_result["query"]
            
            exec_result = self.execute_query(state)
            state["result"] = exec_result["result"]

            answer_result = self.generate_answer(state)
            state["answer"] = answer_result["answer"]
 
            state = self.validate_result(state)
      
            return QueryResult(
                question=state["question"],
                sql_query=state["query"],
                result=state["result"] if state["result"] is not None else pd.DataFrame(),
                answer=str(state["answer"]) if state["answer"] is not None else "",
                row_count=len(state["result"]) if state["result"] is not None else 0
            )
            
        except Exception as e:
            print(f"Error in query_structured: {e}")
            return QueryResult(
                question=user_prompt,
                sql_query="",
                result=pd.DataFrame(),
                answer=f"Error processing query: {str(e)}",
                row_count=0
            )