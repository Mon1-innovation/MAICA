import os
from dotenv import load_dotenv

def load_env(key):
    # Load environment variables from .env file
    load_dotenv()

    # Get environment variables
    result = os.getenv(key)

    # Check if environment variables are present
    if not result:
        raise ValueError("Environment variables are missing.")

    # Return environment variables as dictionary
    return result