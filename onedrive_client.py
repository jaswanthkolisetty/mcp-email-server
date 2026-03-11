import re
import httpx
from config import USER_EMAIL, GRAPH_BASE
from graph_client import get_access_token, _get_client

# Root folder in the user's OneDrive where all attachments are stored
ONEDRIVE_ROOT = "EmailAttachments"


def sanitize(s: str) -> str:
    """Remove characters that are invalid in OneDrive/Windows file paths."""
    return re.sub(r'[<>:"/\\|?*]', "_", s)


def make_onedrive_path(sender_email: str, email_id: str, filename: str) -> str:
    """
    Build the OneDrive storage path for an attachment.

    Structure: EmailAttachments/{sender}/{YYYY}/{MM}/{email_short}_{filename}
    Example:   EmailAttachments/apple_at_mail.com/2025/03/abc123def456_invoice.pdf
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    sender_clean = sanitize(sender_email.replace("@", "_at_"))
    year_month = now.strftime("%Y/%m")
    email_short = email_id[:12]  # Use first 12 chars of email ID for uniqueness
    return f"{ONEDRIVE_ROOT}/{sender_clean}/{year_month}/{email_short}_{filename}"


async def file_exists(onedrive_path: str) -> bool:
    """Check whether a file already exists at the given OneDrive path (for deduplication)."""
    token = await get_access_token()
    r = await _get_client().get(
        f"{GRAPH_BASE}/users/{USER_EMAIL}/drive/root:/{onedrive_path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return r.status_code == 200


async def upload_file(onedrive_path: str, content: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Upload a file to OneDrive using the simple upload endpoint.
    Creates intermediate folders automatically. Overwrites if file already exists.
    Returns the OneDrive path on success.
    """
    token = await get_access_token()
    r = await _get_client().put(
        f"{GRAPH_BASE}/users/{USER_EMAIL}/drive/root:/{onedrive_path}:/content",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        },
        content=content,
    )
    r.raise_for_status()
    return onedrive_path


async def list_files(folder_path: str = None) -> list:
    """
    Recursively list all files under a OneDrive folder.
    Handles pagination via @odata.nextLink.
    Returns a flat list of file dicts with name, size, and last_modified.
    """
    token = await get_access_token()
    path = folder_path or ONEDRIVE_ROOT
    url = f"{GRAPH_BASE}/users/{USER_EMAIL}/drive/root:/{path}:/children"
    results = []

    while url:
        r = await _get_client().get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"$select": "name,size,lastModifiedDateTime,file,folder,parentReference"},
        )
        if r.status_code == 404:
            # Folder doesn't exist yet — return empty list instead of raising
            return []
        r.raise_for_status()
        data = r.json()

        for item in data.get("value", []):
            if "file" in item:
                # Build the full path by combining parent path + filename
                parent = item.get("parentReference", {}).get("path", "").split("root:")[-1].strip("/")
                full_path = f"{parent}/{item['name']}" if parent else item["name"]
                results.append({
                    "name": full_path,
                    "size": item.get("size", 0),
                    "last_modified": item.get("lastModifiedDateTime"),
                })
            elif "folder" in item:
                # Recurse into subfolders to build a flat file list
                sub = await list_files(f"{path}/{item['name']}")
                results.extend(sub)

        # Follow next page if results are paginated
        url = data.get("@odata.nextLink")

    return results


async def read_file(onedrive_path: str) -> bytes:
    """Download and return the raw bytes of a file from OneDrive."""
    token = await get_access_token()
    r = await _get_client().get(
        f"{GRAPH_BASE}/users/{USER_EMAIL}/drive/root:/{onedrive_path}:/content",
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=True,  # Graph API redirects to SharePoint CDN for the actual file
    )
    r.raise_for_status()
    return r.content
