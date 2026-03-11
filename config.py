import os

# Azure AD app credentials for Microsoft Graph API (OAuth2 client credentials flow).
# These must be set as environment variables — never hardcode real values here.
# On Azure Container Apps: az containerapp update --set-env-vars KEY="value"
# Locally: copy .env.example to .env, fill in your values, and load with python-dotenv
TENANT_ID     = os.getenv("TENANT_ID")
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# The mailbox to read emails from
USER_EMAIL = os.getenv("USER_EMAIL")

# Base URL for all Microsoft Graph API calls
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Remote server settings
HOST = os.getenv("HOST", "0.0.0.0")   # Listen on all interfaces so Azure can reach it
PORT = int(os.getenv("PORT", "8000"))

# API key to protect the remote MCP endpoint.
# Set this as an environment variable — do NOT hardcode a real key here.
API_KEY = os.getenv("API_KEY", "")
