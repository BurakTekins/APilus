import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent / "backend"
sys.path.append(str(backend_path))

# Mock Django settings if needed, but llm.py doesn't seem to depend on Django settings
# unless it's imported via something that does.
# Actually, llm.py doesn't import any django stuff.

from APilus.llm import get_vector_db

try:
    print("Attempting to get vector db...")
    db = get_vector_db()
    print("Successfully got vector db!")
    print(f"DB type: {type(db)}")
except Exception as e:
    print(f"Error occurred: {e}")
    import traceback
    traceback.print_exc()
