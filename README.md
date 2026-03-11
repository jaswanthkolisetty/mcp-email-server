# MCP Email Server

A personal email assistant that connects **Claude AI** to your **Microsoft Outlook mailbox** and **OneDrive**. The server runs remotely on **Azure**  your computer just needs internet access.

Once set up, you can ask Claude things like:

- *"Find all emails from Apple with attachments"*
- *"Download the invoice from last month's email to OneDrive"*
- *"Read the PDF attachment from that email and summarize it"*

---

## How It Works

```
Your Computer                  Azure (Cloud)
─────────────                  ─────────────────────────────
Claude Desktop  ──── HTTPS ──▶  MCP Email Server
                                      │
                                      ├──▶ Microsoft Graph API (your emails)
                                      └──▶ OneDrive (file storage)
```

The MCP server runs in the cloud 24/7. You don't need to keep anything running on your machine.

---

## What You Need Before Starting

- **Claude Desktop** → [Download here](https://claude.ai/download)
- **Node.js** (needed for the `mcp-remote` connector) → [Download here](https://nodejs.org) — choose the LTS version
- A **Microsoft 365 account** with Outlook email

---

## Step 1 — Connect Claude Desktop to the Remote Server

1. Open Claude Desktop
2. Go to **Settings** → **Developer** → **Edit Config**
3. Replace the entire contents of the file with:

```json
{
  "mcpServers": {
    "ms-email-server": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://mcp-email-server.thankfulmeadow-426e0542.eastus.azurecontainerapps.io/mcp",
        "--header",
        "X-API-Key:mcp-email-secret-key-2026"
      ]
    }
  }
}
```

> **Mac users:** If `npx` isn't found, replace `"npx"` with `"/opt/homebrew/bin/npx"` (or run `which npx` in Terminal to find the path).

4. Save the file and **restart Claude Desktop** (Cmd+Q / fully quit, then reopen)

---

## Step 2 — Start Using It

Open a new chat in Claude Desktop. You should see a tools icon (hammer or plug) indicating the email tools are connected. Try asking:

| What you can say | What it does |
|---|---|
| *"Search my emails from apple@email.com"* | Lists recent emails from that sender |
| *"Find emails with attachments from last week"* | Filters by date and attachment |
| *"Get details of that email and list its attachments"* | Shows attachment names and IDs |
| *"Download the attachment to OneDrive"* | Saves it to your OneDrive |
| *"Read the PDF I just saved and summarize it"* | Extracts and reads the file content |

---

## Folder Structure in OneDrive

All downloaded attachments are organized automatically:

```
OneDrive/
└── EmailAttachments/
    └── sender_at_email.com/
        └── 2025/
            └── 03/
                └── abc123_invoice.pdf
```

---

## Troubleshooting

**Tools not showing in Claude Desktop**
→ Fully quit and reopen Claude Desktop. Check that Node.js is installed (`node --version` in a terminal).

**"command not found: npx"**
→ Node.js isn't installed or isn't on your PATH. Download it from [nodejs.org](https://nodejs.org) and restart your terminal. On Mac, try using the full path `/opt/homebrew/bin/npx`.

**"401 Unauthorized"**
→ The API key in your config doesn't match. Double-check you copied it exactly with no extra spaces.

**"504 Gateway Timeout"**
→ The Azure container may be starting up (cold start). Wait 30 seconds and try again.

**"404 Not Found" on OneDrive operations**
→ Open [portal.office.com](https://portal.office.com), sign in, and click OneDrive once to activate it. Then retry.

---

## File Overview (For the Curious)

| File | What it does |
|---|---|
| `main.py` | The main server — defines the 5 tools Claude can use, handles auth and routing |
| `graph_client.py` | Talks to Microsoft Graph API to read emails |
| `onedrive_client.py` | Saves and reads files from OneDrive |
| `file_reader.py` | Extracts text from PDFs, Word docs, Excel files, images, etc. |
| `config.py` | Credentials and settings (loaded from environment variables on Azure) |
| `test_auth.py` | Quick test to verify Microsoft Graph API access works |
| `Dockerfile` | Instructions to build and run the server as a Docker container |

---

## For Developers — Deploying Your Own Instance

If you want to run your own copy of this server:

### Prerequisites
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) installed and logged in (`az login`)
- Docker (optional — Azure builds it for you)
- Python 3.11+

### 1. Set Up Azure App Registration

1. Go to [portal.azure.com](https://portal.azure.com) and sign in
2. Search for **"App registrations"** → **+ New registration**
3. Name it `mcp-email-server`, select *"Accounts in this organizational directory only"*, click **Register**
4. Copy the **Application (client) ID** and **Directory (tenant) ID**
5. Go to **Certificates & secrets** → **+ New client secret** → copy the **Value**
6. Go to **API permissions** → **+ Add a permission** → **Microsoft Graph** → **Application permissions**
7. Add `Mail.Read` and `Files.ReadWrite.All`, then click **Grant admin consent**

### 2. Activate OneDrive

Sign in to [portal.office.com](https://portal.office.com) and open OneDrive once to provision your storage.

### 3. Test Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set credentials
export TENANT_ID="your-tenant-id"
export CLIENT_ID="your-client-id"
export CLIENT_SECRET="your-client-secret"
export USER_EMAIL="your@email.com"

# Verify Graph API access
python test_auth.py

# Run the server locally
export API_KEY="your-secret-key"
python main.py
```

### 4. Deploy to Azure Container Apps

```bash
# Create resource group and environment (first time only)
az group create --name mcp-email-rg --location eastus
az containerapp env create --name mcp-email-env --resource-group mcp-email-rg --location eastus

# Deploy (builds and pushes Docker image automatically)
az containerapp up \
  --name mcp-email-server \
  --resource-group mcp-email-rg \
  --environment mcp-email-env \
  --source . \
  --ingress external \
  --target-port 8000

# Set environment variables
az containerapp update \
  --name mcp-email-server \
  --resource-group mcp-email-rg \
  --set-env-vars \
    TENANT_ID="your-tenant-id" \
    CLIENT_ID="your-client-id" \
    CLIENT_SECRET="your-client-secret" \
    USER_EMAIL="your@email.com" \
    API_KEY="your-secret-key"
```

### 5. Update Claude Desktop Config

Replace the URL and API key in the Claude Desktop config (Step 1 above) with your own Azure URL and key.

---

## Health Check

To verify the server is running:

```bash
curl https://your-server-url.azurecontainerapps.io/health
# Expected: {"status": "ok"}
```
