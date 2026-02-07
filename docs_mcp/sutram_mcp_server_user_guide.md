# Remote Access — Sutram MCP Integration

**Version:** 0.83.0
**Date:** 2026-02-06
**Status:** In development

---

## Overview

Sutram Remote Access lets AI assistants and automation tools connect to your projects through the **Model Context Protocol (MCP)**. Once configured, your AI assistant can browse folders, upload files, and manage content in your Sutram projects — all with proper authentication and permissions.

### How it works

```
AI Assistant (Claude, Cursor, etc.)
        |
        | MCP Protocol (HTTPS)
        v
  Sutram MCP Endpoint
    https://sutram.io/mcp
        |
        | Dual Key Authentication
        v
  Your Project (folders, files, content)
```

Two API keys are required for every connection:

| Key | Purpose | Who creates it | Where to find it |
|-----|---------|----------------|------------------|
| **Project Key** (`sk_proj_...`) | Identifies the project | Project owner | Project page or project settings |
| **User Key** (`sk_user_...`) | Identifies you | Each user creates their own | User Settings > API Key |

Both keys must be valid, and you must be an active member of the project (not a viewer) to connect.

---

## Getting Started

### Step 1: Create your personal API Key

1. Go to **Settings** (gear icon in the top-right menu)
2. Click the **API Key** card
3. Click **Create Key**
4. **Copy the key immediately** — it will only be shown once

Your personal key looks like: `sk_user_zQD0BjH56nQhOgX3uxni...`

> **Important:** Store your key securely. If you lose it, you can revoke the old one and create a new key from the same settings page.

### Step 2: Get the project key

The project owner must first enable remote access for the project:

1. Go to **Settings** > **Projects** tab
2. Open the dropdown menu (three dots) next to the project
3. Click **Enable Remote Access**
4. Copy the project key that appears

Once remote access is enabled, any project member (owner, admin, or member) can copy the project key:

1. Open the project
2. Click the green signal icon next to the role badge in the header
3. A modal will show the project key — click the copy button

The project key looks like: `sk_proj_ej8NWMisd2rJgMwAJ22T...`

---

## Configuring Your AI Client

Each Sutram project should have its own local MCP configuration. Since the project key is tied to a specific project, the recommended approach is to create a dedicated workspace folder for each integration and place the `.mcp.json` file there.

**Example:** If you use Sutram to store medical exams, create a local folder for that workflow:

```
~/projects/medical-exams/
└── .mcp.json          ← Sutram keys for your health project
```

This keeps credentials scoped to the right context and avoids mixing unrelated projects.

### Claude Code (CLI) — Recommended

Create a `.mcp.json` file in your workspace folder:

```json
{
  "mcpServers": {
    "sutram": {
      "url": "https://sutram.io/mcp",
      "headers": {
        "x-project-key": "sk_proj_YOUR_PROJECT_KEY",
        "x-user-key": "sk_user_YOUR_USER_KEY"
      }
    }
  }
}
```

Then start Claude Code from that folder. Sutram tools will be available only in that context.

### Cursor

Create a `.cursor/mcp.json` file in your workspace folder:

```json
{
  "mcpServers": {
    "sutram": {
      "url": "https://sutram.io/mcp",
      "headers": {
        "x-project-key": "sk_proj_YOUR_PROJECT_KEY",
        "x-user-key": "sk_user_YOUR_USER_KEY"
      }
    }
  }
}
```

### Claude Desktop

Claude Desktop uses a global configuration file. Add an entry for each Sutram project, using a descriptive name to distinguish them:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sutram-medical-exams": {
      "url": "https://sutram.io/mcp",
      "headers": {
        "x-project-key": "sk_proj_HEALTH_PROJECT_KEY",
        "x-user-key": "sk_user_YOUR_USER_KEY"
      }
    },
    "sutram-construction": {
      "url": "https://sutram.io/mcp",
      "headers": {
        "x-project-key": "sk_proj_WORK_PROJECT_KEY",
        "x-user-key": "sk_user_YOUR_USER_KEY"
      }
    }
  }
}
```

Restart Claude Desktop after saving the file.

> **Tip:** The user key (`sk_user_...`) is the same across all entries — it identifies you. The project key (`sk_proj_...`) changes per project.

### Other MCP Clients

Sutram uses the MCP **Streamable HTTP** transport. Any MCP-compatible client that supports HTTP transport can connect using:

- **Endpoint:** `https://sutram.io/mcp`
- **Method:** POST (JSON-RPC 2.0)
- **Authentication:** Custom headers `x-project-key` and `x-user-key`
- **Protocol version:** 2024-11-05

---

## Available Tools

Once connected, your AI assistant has access to these tools:

### sutram_project_info

Returns information about the current project.

**Parameters:** None

**Example response:**
```json
{
  "project": {
    "id": "a1b2c3d4-...",
    "name": "Construction Site Alpha",
    "description": "Main project documentation",
    "your_role": "member",
    "created_at": "2026-01-15T10:00:00Z"
  }
}
```

---

### sutram_get_folder

Browses the contents of a folder. Omit `folder_id` to list root contents.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `folder_id` | string | No | Folder UUID. Omit for root. |

**Example response:**
```json
{
  "folder": {
    "id": null,
    "name": "Root",
    "path": "/"
  },
  "contents": [
    {
      "type": "folder",
      "id": "f1a2b3c4-...",
      "name": "Reports"
    },
    {
      "type": "file",
      "id": "d5e6f7a8-...",
      "name": "site-plan.pdf",
      "content_type": "application/pdf",
      "size": 2450000
    }
  ]
}
```

---

### sutram_create_folder

Creates a new folder. Supports creating nested hierarchies in a single call.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes* | Folder name (for creating a single folder) |
| `path` | string | Yes* | Slash-separated path for nested creation (e.g., `"A/B/C"`) |
| `parent_folder_id` | string | No | Parent folder UUID. Omit for root level. |

*Use either `name` (single folder) or `path` (nested hierarchy), not both.

**Nested creation:** When using `path`, intermediate folders are created automatically. If any folder in the path already exists, it is reused — the operation is idempotent.

**Example — single folder:**
```json
{ "name": "Reports", "parent_folder_id": "f1a2b3c4-..." }
```

**Example — nested hierarchy:**
```json
{ "path": "Dr. Decio Mion Junior/USG ABDOME TOTAL/2024-12-12" }
```
This creates three folders in one call and returns the deepest one (`2024-12-12`).

---

### sutram_upload_file

Uploads a single file. Content must be base64-encoded.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Filename with extension (e.g., `report.pdf`) |
| `content_base64` | string | Yes | File content encoded in base64 |
| `folder_id` | string | No | Target folder UUID. Omit for root. |
| `content_type` | string | No | MIME type. Auto-detected from extension if omitted. |

**Limits:** Maximum file size, total storage, and bandwidth depend on the project owner's subscription plan.

**Duplicate filenames:** If a file with the same name already exists in the target folder, Sutram automatically renames the new file by adding a numeric suffix: `report.pdf` becomes `report (1).pdf`, then `report (2).pdf`, and so on. The original file is never overwritten.

---

### sutram_upload_batch

Uploads multiple files in a single operation. Processes up to 4 files in parallel.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `files` | array | Yes | Array of file objects (each with `filename`, `content_base64`, optional `content_type`) |
| `folder_id` | string | No | Target folder UUID. Omit for root. |

**Example:**
```json
{
  "files": [
    { "filename": "photo1.jpg", "content_base64": "..." },
    { "filename": "photo2.jpg", "content_base64": "..." },
    { "filename": "notes.txt", "content_base64": "..." }
  ],
  "folder_id": "f1a2b3c4-..."
}
```

---

### sutram_delete

Deletes a file or folder.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `item_id` | string | Yes | File or folder UUID |
| `item_type` | string | Yes | `"file"` or `"folder"` |

---

### sutram_rename

Renames a file or folder.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `item_id` | string | Yes | File or folder UUID |
| `item_type` | string | Yes | `"file"` or `"folder"` |
| `new_name` | string | Yes | New name (for files, include the extension) |

---

### sutram_move_contents

Moves all contents (subfolders and files) from a source folder to a target folder. The source folder is emptied but not deleted. Name conflicts are handled automatically.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source_folder_id` | string | Yes | UUID of the source folder to empty |
| `target_folder_id` | string | Yes | UUID of the target folder to receive contents |

**Name conflict handling:** If a subfolder or file with the same name already exists in the target folder, Sutram automatically renames the moved item by adding a numeric suffix: `Exams` becomes `Exams (1)`, `report.pdf` becomes `report (1).pdf`, and so on.

**Validation rules:**
- Source and target must be different folders
- Target cannot be a subfolder of source (prevents circular moves)
- Both folders must exist in the current project

**Example response:**
```json
{
  "moved": {
    "folders": 3,
    "content_items": 12
  },
  "renamed": {
    "folders": ["Exams (1)"],
    "files": ["report (1).pdf"]
  },
  "source_folder_id": "abc123-...",
  "target_folder_id": "def456-..."
}
```

---

## Limitations

The following operations are not yet available via MCP and must be done through the Sutram web interface. They will be added in future versions:

- **Download:** File content cannot be retrieved (upload-only)
- **Share:** Sharing links cannot be generated
- **Move single item:** Individual files/folders cannot be moved directly (use `sutram_move_contents` to move all contents of a folder)

---

## Permissions

Your MCP access respects the same permissions as the web interface:

| Role | Browse | Upload | Create Folders | Delete |
|------|--------|--------|----------------|--------|
| **Owner** | Yes | Yes | Yes | Yes |
| **Admin** | Yes | Yes | Yes | Yes |
| **Member** | Yes | Yes | Yes | Yes |
| **Viewer** | No MCP access | — | — | — |

> Viewers cannot use remote access. If you need MCP access, ask the project owner to upgrade your role.

---

## Security

- **Keys are independent:** Revoking a user key doesn't affect other users. Revoking a project key disables remote access for everyone on that project.
- **One project key per project:** Only one active project key exists at a time. Regenerating it invalidates the previous one.
- **Keys are never stored in plain text:** Project keys are encrypted. User keys are hashed — they cannot be retrieved after creation.
- **Activity tracking:** Every key records when it was last used.
- **HTTPS only:** All MCP connections use encrypted HTTPS.

### Revoking access

**To revoke your personal key:**
1. Go to Settings > API Key
2. Click "Revoke Key"
3. Create a new one if needed

**To disable remote access for a project** (owner only):
1. Go to Settings > Projects
2. Open the project dropdown
3. Click "Remote Access"
4. Click "Revoke Key"

---

## Troubleshooting

### "Authentication failed"

- Verify both keys are correct and haven't been revoked
- Ensure you are an active member of the project
- Viewers cannot use remote access — check your role on the project page

### "Project key not available"

- The project key may have been revoked by the owner
- Ask the project owner to regenerate it from project settings

### "Storage quota exceeded"

- Your account's storage limit has been reached
- Delete unused files or upgrade your plan

### Tools not appearing in Claude Desktop

- Restart Claude Desktop after editing the configuration file
- Check the JSON syntax is valid (no trailing commas, proper quoting)
- Verify the endpoint URL is correct

### Connection timeout

- Check your internet connection
- Verify the Sutram service is accessible at `https://sutram.io`

---

## Supported File Types

Sutram auto-detects MIME types from file extensions. Common supported formats:

| Category | Extensions |
|----------|------------|
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg` |
| Documents | `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx` |
| Text | `.txt`, `.csv`, `.json`, `.xml`, `.md` |
| Media | `.mp4`, `.mp3`, `.wav` |
| Archives | `.zip` |
| CAD | `.dwg`, `.dxf`, `.rvt`, `.ifc` |

Files with unrecognized extensions are uploaded as `application/octet-stream`.

---

## Examples

### Migrate medical exams from hospital portals

> "Download my ultrasound exam from the hospital portal and organize it in Sutram under the requesting doctor's folder."

The AI assistant will:
1. Access the hospital portal (via browser)
2. Download the PDF report and image files
3. Use `sutram_create_folder` to build the folder structure in one call:
   `Doctor Name / Exam Type / YYYY-MM-DD`
4. Use `sutram_upload_batch` to upload all files at once
5. Clean up temporary local files

This workflow ensures medical data is properly organized and no sensitive files remain on the local computer.

### Upload a local file

> "Upload the file `report.pdf` from my desktop to the 'Reports' folder in Sutram."

Claude will read the file, encode it in base64, use `sutram_get_folder` to find the "Reports" folder, then `sutram_upload_file` to upload it.

### Organize project content

> "Create a folder structure for our construction project: Plans, Reports, and Photos. Then upload these site photos."

Claude will use `sutram_create_folder` for each top-level folder, then `sutram_upload_batch` to upload the photos to the right folder.

### Clean up old files

> "Delete all files in the 'Temp' folder."

Claude will use `sutram_get_folder` to list the folder contents, then `sutram_delete` for each file.

### Reorganize folder structure

> "Move all contents from the '2024' folder into '2024-Archive' to free up space in the main view."

Claude will use `sutram_move_contents` to transfer all subfolders and files from the source to the target folder in a single operation. If any items have conflicting names, they are automatically renamed with numeric suffixes.
