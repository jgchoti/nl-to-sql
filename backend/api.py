import sqlite3
import uuid
import time
import io
import pandas as pd
from flask import Flask, request, jsonify
from upload import Upload
from database import Database
from sql_assistant import SQLAssistApp
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

sessions = {}  # { session_id: { "conn": sqlite_conn, "last_used": ts } }

# --- Config ---
ALLOWED_EXTENSIONS = {"sqlite", "db", "csv"}
SESSION_TTL = 900  # 15 min


@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    upload = Upload(request.files["file"])
    try:
        engine = upload.to_engine() 
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    db = Database(engine)
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"db": db, "last_used": time.time()}

    return jsonify({"session_id": session_id})

@app.route("/api/run-query", methods=["POST"])
def run_query():
    payload = request.get_json()
    session_id = payload.get("session_id")
    sql = payload.get("sql")

    if not session_id or session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400

    db = sessions[session_id]["db"]
    sessions[session_id]["last_used"] = time.time()

    try:
        with db.engine.connect() as conn:
            result = conn.execute(text(sql))
            
            if result.returns_rows:
                rows = result.fetchall()
                columns = list(result.keys()) if rows else []
                return jsonify({
                    "columns": columns, 
                    "rows": [dict(zip(columns, row)) for row in rows]
                })
            else:
                return jsonify({
                    "message": "Query executed successfully", 
                    "rows_affected": result.rowcount
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
@app.route('/api/get-query', methods=['POST'])
def process_query():
    payload = request.get_json()
    session_id = payload.get("session_id")
    sql = payload.get("sql")
    user_question = payload.get('question', '')
    
    if not session_id or session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400
    
    db = sessions[session_id]["db"]
    sessions[session_id]["last_used"] = time.time()
    
    try:
        if len(user_question) < 10:
            return jsonify({
                'success': False,
                'error': 'Question too short. Please ask a clearer question.'
            }), 400
        
        sql_assistant = SQLAssistApp(db)
        result = sql_assistant.query_structured(user_question)
        
        results_data = result['result'].to_dict('records') if not result['result'].empty else []
        
        return jsonify({
            'success': True,
            'result': {
                'question': result['question'],
                'sql_query': result['sql_query'],
                'results': results_data,
                'answer': result['answer'],
                'row_count': result['row_count']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'SQL Assistant API is running'})


@app.before_request
def cleanup_sessions():
    now = time.time()
    expired = [sid for sid, data in sessions.items() if now - data["last_used"] > SESSION_TTL]
    for sid in expired:
        try:
            sessions[sid]["db"].engine.dispose()  
        except Exception:
            pass
        del sessions[sid]

if __name__ == "__main__":
    app.run(debug=True)
