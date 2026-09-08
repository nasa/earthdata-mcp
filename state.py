"""State management and configuration for Earthdata MCP."""

import os
from dotenv import load_dotenv

load_dotenv()

EARTHDATA_CLIENT_ID = os.environ.get("EARTHDATA_CLIENT_ID")
EARTHDATA_CLIENT_SECRET = os.environ.get("EARTHDATA_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://127.0.0.1:5001/oauth/callback")

# This dictionary stores tokens. Maps session_id (or state) -> Access Token
# In a production environment with multiple workers, you would use Redis here.
TOKEN_STORE = {} 
