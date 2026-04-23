# Personal MCP Server - Microsoft 365 + Claude

> Connect your AI to everything Microsoft 365 has to offer. Read emails, manage files, query calendars, search across your organization, all through natural conversation in Cowork.

This project is a personal Model Context Protocol (MCP) server that bridges **Cowork's agentic AI** with the **Microsoft Graph API**. It runs on Azure, stays online 24/7, and gives your AI real access to your Microsoft 365 workspace not just summaries or previews, but actual data it can reason over, act on, and help you with.

The current implementation focuses on email and OneDrive. The architecture is built to extend to anything Microsoft Graph exposes: Calendar, Teams, SharePoint, Contacts, Planner, and beyond.

---

## Why This Matters

Most people use AI as a chat assistant. They copy-paste emails in, ask questions, copy answers out. It works, but it is slow, manual, and the AI never has full context.

This changes that.

When Cowork is connected to your MCP server, it has direct, live access to your actual data. You stop being a middleman. Instead of you bringing information to the AI, the AI reaches into your systems, finds what it needs, and acts on your behalf.

That shift from assistant to agent is where the real productivity gains are.

---

## What You Can Do Today

The server currently exposes five tools to Cowork:

**Email Intelligence**
Ask Cowork to search your inbox with any combination of filters: sender, date range, keywords, or whether the email has attachments. It reads the full email, not just a snippet.

**Attachment Extraction**
Cowork can download attachments from any email directly into your OneDrive, organized automatically by sender and date. No manual downloading, no digging through folders.

**Document Understanding**
Once a file is in OneDrive, Cowork can open it and read the contents — PDFs, Word documents, Excel spreadsheets, CSVs, images. It extracts the text and reasons over it, so you can ask questions about documents you have not even opened yourself.

---

## Real Scenarios - What This Looks Like in Practice

**Scenario 1 - The Weekly Vendor Review**
A procurement manager receives dozens of invoices every week from different suppliers. Instead of opening each one, downloading attachments, and manually checking figures, they open Cowork and say: "Pull all invoices received this month, download them, and give me a summary of total amounts by vendor." Cowork does it in under a minute. What used to take an hour is done before the first coffee.

**Scenario 2 - The Contract Audit**
A legal team needs to review all contracts signed in Q1. The contracts are scattered across email attachments from multiple senders. A paralegal tells Cowork: "Find all emails from our external counsel between January and March that have PDF attachments, download them, and flag any that mention termination clauses." Cowork searches, downloads, reads each document, and returns a structured report.

**Scenario 3 - The Sales Follow-Up**
A sales representative has been in back-and-forth emails with a prospect for two weeks. Before a big call, they ask Cowork: "Summarize everything exchanged with this prospect, pull any documents they sent, and highlight any commitments we made." Cowork reads the entire thread and the attachments, then gives a clean briefing in seconds.

**Scenario 4 - The Executive Briefing**
A chief of staff needs a Monday morning summary for the executive team. They set up a recurring Cowork task: every Monday at 8am, search all emails from the weekend across key domains, pull any attachments, and generate a structured briefing document. It is waiting in OneDrive before anyone walks into the office.

**Scenario 5 - The Compliance Check**
A compliance officer needs to verify that all required reports were submitted on time. They ask Cowork: "Find every email from our reporting team in the last quarter that contains an Excel attachment, download them all, and confirm the submission dates match our schedule." Cowork cross-references the email timestamps with the file contents and flags any gaps.

---

## Architecture

```
Your Computer                       Azure (Cloud)
─────────────                       ──────────────────────────────────
Cowork / Claude Desktop             MCP Email Server
  │                                   │
  └── mcp-remote (local proxy) ──────▶│  MCPApp (ASGI)
       HTTPS + X-API-Key              │  ├── /health
                                      │  ├── API key auth
                                      │  ├── Host header normalization
                                      │  └── /mcp (FastMCP)
                                      │       ├── search_emails
                                      │       ├── get_email_details
                                      │       ├── download_attachment_to_onedrive
                                      │       ├── list_onedrive_files
                                      │       └── read_onedrive_file
                                      │
                              ┌───────┴────────┐
                              ▼                ▼
                    Microsoft Graph API     OneDrive
                    (OAuth2 · Mail.Read)    (EmailAttachments/)
                    (Files.ReadWrite.All)
```

**Transport:** FastMCP · Streamable HTTP
**Platform:** Azure Container Apps
**Auth:** OAuth2 Client Credentials (Azure AD) + X-API-Key middleware

---

## Connecting to Cowork

Install Node.js from [nodejs.org](https://nodejs.org), then open Cowork's developer settings and add:

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

Restart Cowork. The tools will appear automatically.

---

## OneDrive Storage Structure

All downloaded attachments are organized without any manual effort:

```
OneDrive/
└── EmailAttachments/
    └── sender@company.com/
        └── 2026/
            └── 03/
                └── abc123_invoice.pdf
```

---

## Extending to the Full Microsoft 365 Surface

The current tools cover email and files. Microsoft Graph exposes far more, and this server is designed to grow. Adding a new capability means writing one function. Some natural extensions:

- **Calendar** - let Cowork read your schedule, find free slots, summarize upcoming meetings
- **Teams** - search messages, pull files shared in channels
- **SharePoint** - query document libraries across your organization
- **Contacts** - look up colleagues, enrich email context with org data
- **Planner / Tasks** - create and track tasks from email conversations automatically

Each of these follows the same pattern already established here: authenticate once via Azure AD, call the Graph API, return structured data to Cowork.

---

## Deploying Your Own Instance

### Prerequisites

- Azure CLI installed and authenticated via `az login`
- An Azure subscription
- A Microsoft 365 account

### 1. Register an Azure AD Application

1. Go to [portal.azure.com](https://portal.azure.com) and open **App registrations**
2. Create a new registration, select single-tenant, and copy the **Client ID** and **Tenant ID**
3. Under **Certificates and secrets**, create a new client secret and copy the value immediately
4. Under **API permissions**, add `Mail.Read` and `Files.ReadWrite.All` as Application permissions
5. Click **Grant admin consent**

### 2. Activate OneDrive

Sign in to [portal.office.com](https://portal.office.com) and open OneDrive once to provision your storage.

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```
TENANT_ID=your-azure-tenant-id
CLIENT_ID=your-azure-client-id
CLIENT_SECRET=your-azure-client-secret
USER_EMAIL=your@email.com
API_KEY=choose-a-strong-random-key
```

### 4. Verify Access

```bash
pip install -r requirements.txt
python test_auth.py
```

### 5. Deploy to Azure

```bash
az group create --name mcp-email-rg --location eastus
az containerapp env create --name mcp-email-env --resource-group mcp-email-rg --location eastus

az containerapp up \
  --name mcp-email-server \
  --resource-group mcp-email-rg \
  --environment mcp-email-env \
  --source . \
  --ingress external \
  --target-port 8000

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

### 6. Update Cowork Config

Replace the server URL and API key in your Cowork MCP config with your own Azure deployment URL.

---

## Codebase Overview

| File | Purpose |
|---|---|
| `main.py` | ASGI server, request pipeline, all five MCP tools |
| `graph_client.py` | Microsoft Graph API client, OAuth2 token management |
| `onedrive_client.py` | OneDrive read and write operations |
| `file_reader.py` | Text extraction from PDF, Word, Excel, CSV, images |
| `config.py` | Configuration loaded entirely from environment variables |
| `test_auth.py` | Validates Graph API credentials and mailbox access |
| `Dockerfile` | Container definition for Azure deployment |

---

## Health Check

```bash
curl https://your-server-url.azurecontainerapps.io/health
```

Expected response: `{"status": "ok"}`
