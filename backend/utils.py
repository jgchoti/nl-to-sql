from pprint import pprint
import pandas as pd

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


