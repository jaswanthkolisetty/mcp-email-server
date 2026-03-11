from typing import Optional

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import API_KEY, HOST, PORT
from graph_client import (
    search_emails as graph_search_emails,
    get_email_details as graph_get_email_details,
    download_attachment as graph_download_attachment,
)
from onedrive_client import (
    make_onedrive_path,
    file_exists,
    upload_file,
    list_files,
    read_file,
)
from file_reader import extract_text

mcp = FastMCP("Email MCP Server")


class HostHeaderMiddleware:
    """Rewrite the Host header to 'localhost' before the MCP SDK security check.

    MCP's transport security only allows 'localhost' by default. Azure Container
    Apps forwards the public domain as the Host header, which causes a 421.
    This middleware normalizes it so the MCP security check passes.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope["headers"] = [
                (b"host", b"localhost:8000") if name == b"host" else (name, value)
                for name, value in scope.get("headers", [])
            ]
        await self.app(scope, receive, send)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject any request that doesn't carry the correct X-API-Key header."""

    async def dispatch(self, request: Request, call_next):
        # Allow health check through without auth so Azure can probe the container
        if request.url.path == "/health":
            return await call_next(request)

        if not API_KEY:
            # If no API key is configured, block all requests for safety
            return Response("API_KEY environment variable is not set", status_code=500)

        if request.headers.get("X-API-Key") != API_KEY:
            return Response("Unauthorized", status_code=401)

        return await call_next(request)


@mcp.tool()
async def search_emails(
    sender: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keyword: Optional[str] = None,
    has_attachment: Optional[bool] = None,
    limit: int = 20,
) -> str:
    """
    Search emails in the mailbox. All filters are optional and can be combined.

    Args:
        sender: Filter by sender email address (e.g. apple@mail.com)
        date_from: Start date in YYYY-MM-DD format (e.g. 2025-03-01)
        date_to: End date in YYYY-MM-DD format (e.g. 2025-03-07)
        keyword: Word to search in subject
        has_attachment: If True, only return emails that have attachments
        limit: Max number of results to return (default 20)
    """
    emails = await graph_search_emails(
        sender=sender,
        date_from=date_from,
        date_to=date_to,
        keyword=keyword,
        has_attachment=has_attachment,
        limit=limit,
    )

    if not emails:
        return "No emails found matching the given criteria."

    lines = [f"Found {len(emails)} email(s):\n"]
    for i, e in enumerate(emails, 1):
        attachment_flag = " [HAS ATTACHMENT]" if e["has_attachment"] else ""
        lines.append(
            f"{i}. Subject: {e['subject']}{attachment_flag}\n"
            f"   From: {e['from_name']} <{e['from']}>\n"
            f"   Received: {e['received']}\n"
            f"   Preview: {e['preview'][:120]}\n"
            f"   Email ID: {e['id']}\n"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_email_details(email_id: str) -> str:
    """
    Get full details of a specific email and list its attachments with their IDs.

    Args:
        email_id: The Email ID returned from search_emails
    """
    details = await graph_get_email_details(email_id)

    lines = [
        f"Subject:  {details['subject']}",
        f"From:     {details['from']}",
        f"Received: {details['received']}",
        f"\nAttachments ({len(details['attachments'])}):",
    ]

    if not details["attachments"]:
        lines.append("  (no attachments)")
    else:
        for att in details["attachments"]:
            size_kb = att["size"] // 1024
            lines.append(
                f"  - Name: {att['name']}\n"
                f"    Size: {size_kb} KB  |  Type: {att['content_type']}\n"
                f"    Attachment ID: {att['id']}"
            )

    return "\n".join(lines)


@mcp.tool()
async def download_attachment_to_onedrive(
    email_id: str,
    attachment_id: str,
    sender_email: str,
) -> str:
    """
    Download an attachment from an email and store it in OneDrive (EmailAttachments folder).
    Skips the download if the file already exists (deduplication).

    Args:
        email_id: Email ID from search_emails
        attachment_id: Attachment ID from get_email_details
        sender_email: Sender's email address (used to organize files in storage)
    """
    # Step 1: Download attachment bytes from Microsoft Graph
    try:
        content, filename, content_type = await graph_download_attachment(email_id, attachment_id)
    except Exception as e:
        return f"ERROR downloading attachment from Graph API: {type(e).__name__}: {e}"

    # Step 2: Build the destination path and skip if already stored
    onedrive_path = make_onedrive_path(sender_email, email_id, filename)
    if await file_exists(onedrive_path):
        return f"Already exists in OneDrive, skipping download.\nPath: {onedrive_path}"

    # Step 3: Upload to OneDrive
    try:
        await upload_file(onedrive_path, content, content_type)
    except Exception as e:
        return f"ERROR uploading to OneDrive: {type(e).__name__}: {e}"

    return (
        f"Downloaded and stored in OneDrive successfully.\n"
        f"File: {filename} ({len(content) // 1024} KB)\n"
        f"OneDrive path: {onedrive_path}"
    )


@mcp.tool()
async def list_onedrive_files(folder_path: Optional[str] = None) -> str:
    """
    List files stored in OneDrive under the EmailAttachments folder.

    Args:
        folder_path: Optional subfolder path to filter results.
                     Examples:
                       - 'EmailAttachments/apple_at_mail.com' → files from that sender
                       - 'EmailAttachments/apple_at_mail.com/2025/03' → files from March 2025
                       - Leave empty to list all files
    """
    files = await list_files(folder_path)

    if not files:
        msg = "No files found in OneDrive"
        return msg + (f" at '{folder_path}'." if folder_path else ".")

    lines = [f"Found {len(files)} file(s):\n"]
    for f in files:
        size_kb = (f["size"] or 0) // 1024
        lines.append(f"  - {f['name']}  ({size_kb} KB, modified: {f['last_modified']})")
    return "\n".join(lines)


@mcp.tool()
async def read_onedrive_file(onedrive_path: str) -> str:
    """
    Read the content of a file from OneDrive and return it for analysis.
    Supports PDF, Excel (.xlsx), Word (.docx), CSV, TXT, and images.

    Args:
        onedrive_path: Full path from list_onedrive_files (e.g. EmailAttachments/apple_at_mail.com/2025/03/abc_invoice.pdf)
    """
    content = await read_file(onedrive_path)
    filename = onedrive_path.split("/")[-1]
    extracted = extract_text(content, filename)
    return f"=== {filename} ===\n\n{extracted}"


class MCPApp:
    """
    Top-level ASGI app that wraps the MCP server with:
    - Lifespan passthrough (required for MCP session manager initialization)
    - /health endpoint (no auth required, used by Azure container probes)
    - API key authentication on all other routes
    - Host header rewrite (Azure forwards the public domain; MCP only allows localhost)
    """

    def __init__(self, mcp_asgi):
        self.mcp_asgi = mcp_asgi

    async def __call__(self, scope, receive, send):
        # Pass lifespan events directly so MCP's session manager initializes properly
        if scope["type"] == "lifespan":
            await self.mcp_asgi(scope, receive, send)
            return

        if scope["type"] == "http":
            path = scope.get("path", "")

            # Health check: allow through without auth
            if path == "/health":
                from starlette.responses import JSONResponse
                response = JSONResponse({"status": "ok"})
                await response(scope, receive, send)
                return

            # API key check
            headers = dict(scope.get("headers", []))
            incoming_key = headers.get(b"x-api-key", b"").decode()
            if not API_KEY:
                from starlette.responses import Response
                await Response("API_KEY not configured", status_code=500)(scope, receive, send)
                return
            if incoming_key != API_KEY:
                from starlette.responses import Response
                await Response("Unauthorized", status_code=401)(scope, receive, send)
                return

            # Fix host header so MCP SDK security check passes.
            # FastMCP allows "localhost:*" (any port) — must include port number.
            scope["headers"] = [
                (b"host", b"localhost:8000") if name == b"host" else (name, value)
                for name, value in scope.get("headers", [])
            ]

        await self.mcp_asgi(scope, receive, send)


if __name__ == "__main__":
    app = MCPApp(mcp.streamable_http_app())
    uvicorn.run(app, host=HOST, port=PORT)
