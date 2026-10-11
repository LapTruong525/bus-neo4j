import os

from dotenv import load_dotenv

# Đọc .env ở thư mục gốc dự án (nếu có)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
