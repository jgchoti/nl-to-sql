import sqlite3
import uuid
import time
import io
import os
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from upload import Upload
    from database import Database
    from sql_assistant import SQLAssistApp
    from langchain_community.utilities.sql_database import SQLDatabase
    logger.info("Successfully imported all modules")
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    raise

app = Flask(__name__)

CORS(app, 
     origins=[
         "http://localhost:3000",
         "https://sql-assist.vercel.app",  
     ],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     supports_credentials=True
)

sessions = {}  # { session_id: { "db": Database, "langchain_db": SQLDatabase, "last_used": ts } }

# --- Config ---
ALLOWED_EXTENSIONS = {"sqlite", "db", "csv"}
SESSION_TTL = 900  # 15 min

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "message": "SQL Assistant API",
        "version": "1.0.0",
        "server": "Flask + Gunicorn",
        "endpoints": [
            "/api/health",
            "/api/upload",
            "/api/run-query", 
            "/api/get-query"
        ]
    }), 200

@app.route("/api/upload", methods=["POST"])
def upload_file():
    try:
        logger.info("Processing file upload...")
        
        if "file" not in request.files:
            return jsonify({"error": "No file"}), 400

        upload = Upload(request.files["file"])
        try:
            engine = upload.to_engine() 
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        db = Database(engine)
        
        try:
            langchain_db = SQLDatabase(engine)
            logger.info("Created LangChain SQLDatabase successfully")
        except Exception as e:
            logger.error(f"Failed to create LangChain SQLDatabase: {e}")
            return jsonify({"error": f"Database initialization failed: {str(e)}"}), 500

        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "db": db, 
            "langchain_db": langchain_db,
            "last_used": time.time()
        }

        logger.info(f"File uploaded successfully, session: {session_id}")
        return jsonify({"session_id": session_id})
    
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

@app.route("/api/run-query", methods=["POST"])
def run_query():
    try:
        payload = request.get_json()
        
        if not payload:
            return jsonify({"error": "No JSON payload"}), 400
            
        session_id = payload.get("session_id")
        sql = payload.get("sql")

        if not session_id or session_id not in sessions:
            return jsonify({"error": "Invalid session"}), 400

        if not sql:
            return jsonify({"error": "SQL query required"}), 400

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
            logger.error(f"Query execution error: {e}")
            return jsonify({"error": str(e)}), 400
    
    except Exception as e:
        logger.error(f"Run query error: {e}")
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    
@app.route('/api/get-query', methods=['POST'])
def process_query():
    try:
        logger.info("Processing natural language query...")
        
        payload = request.get_json()
        
        if not payload:
            return jsonify({"error": "No JSON payload"}), 400
            
        session_id = payload.get("session_id")
        user_question = payload.get('question', '')
        
        logger.info(f"Session: {session_id}, Question: {user_question[:100]}...")
        
        if not session_id or session_id not in sessions:
            return jsonify({
                'success': False,
                'error': 'Invalid session. Please upload a file first.'
            }), 400
        
        if len(user_question) < 10:
            return jsonify({
                'success': False,
                'error': 'Question too short. Please ask a clearer question.'
            }), 400
        
        langchain_db = sessions[session_id]["langchain_db"]
        sessions[session_id]["last_used"] = time.time()
        
        try:
            sql_assistant = SQLAssistApp(langchain_db)  
            
            logger.info("Executing query_structured...")
            result = sql_assistant.query_structured(user_question)
            

            if result.result is not None and not result.result.empty:
                results_data = result.result.to_dict('records')
            else:
                results_data = []
            
            logger.info(f"Query processed successfully. Found {len(results_data)} results")
            
            return jsonify({
                'success': True,
                'result': {
                    'question': result.question,
                    'sql_query': result.sql_query,
                    'results': results_data,
                    'answer': result.answer,
                    'row_count': result.row_count
                }
            })
            
        except Exception as e:
            logger.error(f"SQLAssistApp error: {e}")
            return jsonify({
                'success': False, 
                'error': f"Failed to process question: {str(e)}"
            }), 500
    
    except Exception as e:
        logger.error(f"Process query error: {e}")
        return jsonify({
            'success': False, 
            'error': f"Request failed: {str(e)}"
        }), 500
    
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        test_passed = True
        error_msg = ""
        
        try:
            from langchain_community.utilities.sql_database import SQLDatabase
        except Exception as e:
            test_passed = False
            error_msg = f"LangChain import failed: {e}"
            
        return jsonify({
            'status': 'healthy' if test_passed else 'degraded',
            'message': 'SQL Assistant API is running',
            'modules_loaded': test_passed,
            'error': error_msg if not test_passed else None,
            'sessions_active': len(sessions)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.before_request
def cleanup_sessions():
    try:
        now = time.time()
        expired = [sid for sid, data in sessions.items() if now - data["last_used"] > SESSION_TTL]
        
        for sid in expired:
            try:
                # Clean up both database connections
                sessions[sid]["db"].engine.dispose()
                # LangChain SQLDatabase cleanup
                if hasattr(sessions[sid]["langchain_db"], '_engine'):
                    sessions[sid]["langchain_db"]._engine.dispose()
                logger.info(f"Cleaned up expired session: {sid}")
            except Exception as e:
                logger.error(f"Error cleaning up session {sid}: {e}")
            finally:
                sessions.pop(sid, None)
    except Exception as e:
        logger.error(f"Session cleanup error: {e}")

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)