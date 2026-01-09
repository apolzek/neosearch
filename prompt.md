# Neosearch prompt

## Authentication & Access Control

### Routes
- `/` - Public search page (unauthenticated users can search public registries)
- `/login` - Login screen using username/password or email/password
- `/register` - Registration screen requiring username, password, and email
- `/home?user=username` - User's personal search page (redirect after login)
- `/home?user=username&registry=url_encoded`

### Access Levels
- **Unauthenticated users**: Can search and view public registries only
- **Authenticated users**: Can search both public and private registries (their own + public from others)
- **Registry visibility**: 
  - Default: Public (anyone can access)
  - Private: Only accessible to owner via JWT token validation
  - Private registries return 404 for unauthorized users

## Main Search Interface (Default Page)

### Search Bar
- **Primary function**: Substring search across all fields (url, description, tags, category)
- **Fast search algorithm**: Real-time filtering as user types
- **URL sharing**: When a user selects a registry, add it to query params
  - Example: `/home?user=username&registry=url_encoded`
  - Public registries can be accessed by anyone via this shared URL
  - Private registries require authentication (JWT validation)

### Action Buttons
- **Top-right Import button** (+): Opens modal for:
  - File upload (JSON)
  - URL import (HTTP/HTTPS raw JSON)
- **Per-registry actions** (visible on hover or selection):
  - **X button**: Delete (shows confirmation modal)
  - **Pencil icon**: Edit (opens edit modal)
  - **Star icon**: Toggle favorite status

### Modals
- **Add Registry Modal**: Form with fields (url required, others optional)
- **Edit Registry Modal**: Pre-filled form to update existing registry
- **Delete Confirmation Modal**: "Are you sure you want to delete [URL]?"
- **Import Modal**: Choose between file upload or URL input

## Repository Management

### Import Rules (Atomic Operations)
- **All-or-nothing**: If any registry fails validation, entire import is rejected
- **Validation checks**:
  - Valid JSON format
  - Character limits per field
  - Mandatory field: `url`
  - URL format validation (HTTP/HTTPS)
  - Duplicate detection via hash mechanism
- **Import sources**:
  - JSON file upload
  - HTTP/HTTPS link to raw JSON (validate hash to prevent duplicates)
- **Access requirement**: User must be logged in to import

### User Repository
- Each user has a personal collection of registries stored in the database
- Registries can be marked public or private
- Users can only edit/delete their own registries

## Registry Structure

### User-Facing Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| url | String | Yes | - | Must be valid HTTP/HTTPS |
| description | String | No | Empty | Optional context |
| tags | Array | No | [] | Keywords for searching |
| category | String | No | Empty | Organizational label |
| favorite | Boolean | No | false | User must manually mark |
| public | Boolean | No | true | Visibility setting |

**Note**: Users can add a URL with only the `url` field; all others are optional.

### Database Fields (System-Managed, Hidden from Users)
- `id` - Unique identifier
- `userId` - Owner reference
- `dateAdded` - Timestamp of creation
- `dateModified` - Timestamp of last update
- `dateDeleted` - Timestamp of soft deletion (null if active)
- `visitCount` - Number of times the registry was clicked/selected

**Note**: These fields are not displayed in search results or forms.

## Example Import JSON
```json
[
    {
        "url": "http://history-artifacts.com",
        "description": "Artifacts and history discoveries",
        "tags": ["history", "artifacts", "discoveries"],
        "category": "LABY",
        "favorite": true,
        "public": true
    },
    {
        "url": "https://github.com/kubernetes/kubernetes",
        "description": "Production-Grade Container Scheduling and Management",
        "tags": ["kubernetes", "containers", "devops", "cloud"],
        "category": "CNCF",
        "favorite": false,
        "public": false
    }
]
```

Important points

- Should search results show registries from other users (public ones)? R: No
- How should results be sorted? (Most visited, recently added, alphabetical, relevance score?)R: alphabetical
- Display format are implemented, but add bar where superpass 10 itens
- dont paginate, use list with a bard order by aproximate string
- When sharing a URL with query params, should it:
  - Show just that one registry? Yes (user can just share a especific registry not a query research or nothing like it)
- Can users browse other users' public registries? Acessing user path yes, but on public research no
- Should there be a "public feed" or "explore" page? No
- Are categories predefined or user-created? Predefined
- Should there be category/tag suggestions while typing? Yes, autocomplete is very good here
- Can users filter by multiple tags simultaneously? Yes, he can use just a string like 'google'but can use especific query like #tag=dasuhjsdu, #tag=jaja, #url=sadas.. 

- What hashing algorithm for duplicate detection? (MD5, SHA256?) R: most secure
- Rate limiting for imports (max imports per hour/day)? R: yes, max = 100
- Maximum registries per user? R: 1000
- Maximum file size for JSON imports?  R: 1000
- URL validation: whitelist/blacklist certain domains? No

- Authentication: JWT
- 



----------------------

- Should there be keyboard shortcuts? (e.g., "/" to focus search, "Ctrl+K" for quick add) 
- Autocomplete suggestions while typing in search?
- Recent searches history?
- Undo/redo for deletions?
- Bulk operations (select multiple registries to delete/edit at once)?

### 6. Data Management
- Can users export their registries back to JSON?
- Recycle bin for deleted items? (How long to keep: 30 days?)
- Backup/restore functionality?
- Import history log?

### 7. Technology Stack
- Frontend: React, Vue, Angular, or Svelte?
- Backend: Node.js (Express/Fastify), Python (Django/FastAPI), Go, or Java?
- Database: PostgreSQL, MySQL, MongoDB, or SQLite?
- Authentication: JWT, OAuth, or session-based?
- Search engine: Built-in database search or dedicated solution (Elasticsearch, Algolia)?
- Deployment: Docker, cloud platform (AWS, GCP, Vercel)?

### 8. Additional Features (Future Considerations)
- Browser extension for quick bookmarking?
- API for third-party integrations?
- Collaborative folders (shared registries between users)?
- Comments or notes on registries?
- Registry versioning (track changes over time)?
- Analytics dashboard (most visited, trending registries)?

