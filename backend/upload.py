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

        # Save uploaded file to a temporary location
        temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.db")
        self.file_storage.save(temp_path)

        # Create a new in-memory database
        mem_conn = sqlite3.connect(":memory:")
        disk_conn = sqlite3.connect(temp_path)

        # Copy all tables from uploaded DB → memory
        disk_conn.backup(mem_conn)

        disk_conn.close()
        os.remove(temp_path)

        # Give each in-memory DB a unique name so SQLAlchemy can attach
        mem_id = str(uuid.uuid4())
        uri = f"file:{mem_id}?mode=memory&cache=shared"

        # Important: keep the connection alive in memory
        sqlite3.connect(uri, uri=True, check_same_thread=False)

        # Return SQLAlchemy engine bound to this in-memory DB
        engine = create_engine(f"sqlite:///{uri}", connect_args={"uri": True})
        return engine

    
   
        

