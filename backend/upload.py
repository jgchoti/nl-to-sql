from sqlalchemy import create_engine
import sqlite3
import os
import uuid
import tempfile

ALLOWED_EXTENSIONS = {'sqlite', 'sql', 'db', 'csv'}


class Upload:
    def __init__(self, file_storage):
        self.file_storage = file_storage
        self.filename = file_storage.filename

    def allowed_file(self):
        return '.' in self.filename and \
               self.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
               
    def to_engine(self):
        if not self.allowed_file():
            raise ValueError("Invalid file type")
        temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.db")
        self.file_storage.save(temp_path)
        disk_conn = sqlite3.connect(temp_path)
        disk_conn.close()
        engine = create_engine(f"sqlite:///{temp_path}")
        return engine


    
   
        

