from pathlib import Path
import requests
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from langchain_community.utilities.sql_database import SQLDatabase

class Database:
    def __init__(self, engine):
        self.engine = engine

    def create_sql_database(self) -> SQLDatabase:
        return SQLDatabase(self.engine)
