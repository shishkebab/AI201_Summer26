import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "llama-3.3-70b-versatile"
MAX_TOOL_ROUNDS = 8
DEFAULT_USER_ID = "demo_user"
