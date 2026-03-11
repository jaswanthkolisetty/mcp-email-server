import asyncio
import base64
import json
import httpx
from graph_client import get_access_token
from config import USER_EMAIL, GRAPH_BASE


async def test():
    print("1. Getting access token...")
    token = await get_access_token()
    print("   OK - token obtained")

    print("\n2. Checking app permissions on token...")
    payload = token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    claims = json.loads(base64.b64decode(payload))
    roles = claims.get("roles", [])
    print(f"   Roles in token: {roles}")
    if "Mail.Read" not in roles:
        print("   WARNING: Mail.Read not in token roles — admin consent may be missing")

    print(f"\n3. Checking user exists: {USER_EMAIL}...")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{GRAPH_BASE}/users/{USER_EMAIL}",
            headers={"Authorization": f"Bearer {token}"},
        )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   User: {data.get('displayName')} / {data.get('mail')}")
    else:
        print(f"   Error: {r.text[:300]}")

    print(f"\n4. Reading mailbox messages...")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{GRAPH_BASE}/users/{USER_EMAIL}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"$top": 1, "$select": "subject"},
        )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        msgs = r.json().get("value", [])
        print(f"   OK - found {len(msgs)} message(s)")
    else:
        print(f"   Error: {r.text[:300]}")


asyncio.run(test())
