from langfuse import Langfuse
import os
from dotenv import load_dotenv

load_dotenv("backend/.env")

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST")
)

print(dir(langfuse))
