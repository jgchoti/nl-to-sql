from database import Database
from sql_assistant import SQLAssistApp
from utils import display_results, chinook_test_questions, sakila_test_questions, general_test_questions

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


