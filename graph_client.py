import time
import base64
import httpx
from config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, USER_EMAIL, GRAPH_BASE

# OAuth2 token endpoint for client credentials flow
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

# In-memory token cache to avoid fetching a new token on every request
_token_cache = {"token": None, "expires_at": 0}

# Shared HTTP client — reuses TCP connections across all API calls
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return the shared httpx client, creating it on first use."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=60.0)
    return _http_client


async def get_access_token() -> str:
    """
    Return a valid Bearer token, fetching a new one only when expired.
    Refreshes 60 seconds before expiry to avoid using a token that's about to expire.
    """
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    response = await _get_client().post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    })
    response.raise_for_status()
    data = response.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data["expires_in"]
    return _token_cache["token"]


async def search_emails(
    sender: str = None,
    date_from: str = None,
    date_to: str = None,
    keyword: str = None,
    has_attachment: bool = None,
    limit: int = 20,
) -> list:
    """
    Search the mailbox using OData filters. All parameters are optional.
    Returns a list of simplified email dicts.
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Build OData $filter string from whichever filters were provided
    filters = []
    if sender:
        filters.append(f"from/emailAddress/address eq '{sender}'")
    if date_from:
        filters.append(f"receivedDateTime ge {date_from}T00:00:00Z")
    if date_to:
        filters.append(f"receivedDateTime le {date_to}T23:59:59Z")
    if has_attachment is True:
        filters.append("hasAttachments eq true")
    if keyword:
        filters.append(f"contains(subject, '{keyword}')")

    params = {
        "$top": limit,
        "$select": "id,subject,from,receivedDateTime,hasAttachments,bodyPreview",
        "$orderby": "receivedDateTime desc",
    }
    if filters:
        params["$filter"] = " and ".join(filters)

    response = await _get_client().get(
        f"{GRAPH_BASE}/users/{USER_EMAIL}/messages",
        headers=headers,
        params=params,
    )
    response.raise_for_status()
    data = response.json()

    return [
        {
            "id": msg["id"],
            "subject": msg.get("subject", "(no subject)"),
            "from": msg["from"]["emailAddress"]["address"],
            "from_name": msg["from"]["emailAddress"].get("name", ""),
            "received": msg["receivedDateTime"],
            "has_attachment": msg.get("hasAttachments", False),
            "preview": msg.get("bodyPreview", "")[:200],
        }
        for msg in data.get("value", [])
    ]


async def get_email_details(email_id: str) -> dict:
    """
    Fetch full metadata for a single email, plus a list of its attachments.
    Makes a second API call only if the email actually has attachments.
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = await _get_client().get(
        f"{GRAPH_BASE}/users/{USER_EMAIL}/messages/{email_id}",
        headers=headers,
        params={"$select": "id,subject,from,receivedDateTime,hasAttachments"},
    )
    response.raise_for_status()
    msg = response.json()

    attachments = []
    if msg.get("hasAttachments"):
        # Fetch attachment metadata (not the file content)
        att_response = await _get_client().get(
            f"{GRAPH_BASE}/users/{USER_EMAIL}/messages/{email_id}/attachments",
            headers=headers,
            params={"$select": "id,name,size,contentType"},
        )
        att_response.raise_for_status()
        for att in att_response.json().get("value", []):
            attachments.append({
                "id": att["id"],
                "name": att.get("name", "attachment"),
                "size": att.get("size", 0),
                "content_type": att.get("contentType", "application/octet-stream"),
            })

    return {
        "id": msg["id"],
        "subject": msg.get("subject", "(no subject)"),
        "from": msg["from"]["emailAddress"]["address"],
        "received": msg["receivedDateTime"],
        "attachments": attachments,
    }


async def download_attachment(email_id: str, attachment_id: str) -> tuple:
    """
    Download an attachment and return (content_bytes, filename, content_type).

    Small attachments are returned inline as base64 in the metadata response.
    Large attachments (where contentBytes is absent) are fetched via the /$value endpoint.
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    url = f"{GRAPH_BASE}/users/{USER_EMAIL}/messages/{email_id}/attachments/{attachment_id}"
    response = await _get_client().get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    filename = data.get("name", "attachment")
    content_type = data.get("contentType", "application/octet-stream")

    if "contentBytes" in data and data["contentBytes"]:
        # Small attachment: content is base64-encoded in the JSON response
        content_bytes = base64.b64decode(data["contentBytes"])
    else:
        # Large attachment: fetch raw bytes from the $value endpoint
        r = await _get_client().get(f"{url}/$value", headers=headers)
        r.raise_for_status()
        content_bytes = r.content

    return content_bytes, filename, content_type
