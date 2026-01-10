from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import time
import requests
from datetime import timedelta

# Import our modules
import database as db
import auth
from models import (
    UserCreate, UserLogin, UserResponse, Token,
    BookmarkCreate, BookmarkResponse,
    RepositoryCreate, RepositoryResponse, RepositoryImportResult
)


app = FastAPI(title="NeoSearch", version="2.0.0")


# ============================================
# MIDDLEWARE
# ============================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# Rate Limiting Middleware
RATE_LIMIT_DURATION = 60  # 1 minute
RATE_LIMIT_REQUESTS = 60  # 60 requests per minute
request_history = {}


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    client_ip = request.client.host
    current_time = time.time()

    # Clean old requests
    for ip in list(request_history.keys()):
        request_history[ip] = [t for t in request_history[ip] if current_time - t < RATE_LIMIT_DURATION]
        if not request_history[ip]:
            del request_history[ip]

    # Check rate limit
    if client_ip in request_history and len(request_history[client_ip]) >= RATE_LIMIT_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."}
        )

    # Add request to history
    if client_ip not in request_history:
        request_history[client_ip] = []
    request_history[client_ip].append(current_time)

    # Process request
    response = await call_next(request)
    return response


# ============================================
# STARTUP/SHUTDOWN EVENTS
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    db.init_database()
    print("Database initialized successfully")


# ============================================
# PUBLIC ENDPOINTS
# ============================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0"}


@app.post("/auth/register", response_model=Token)
def register(user: UserCreate):
    """Register a new user"""
    # Check if user already exists
    existing_user = db.get_user_by_username(user.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Hash password and create user
    password_hash = auth.get_password_hash(user.password)
    user_id = db.create_user(user.username, password_hash)

    # Create access token
    access_token = auth.create_access_token(
        data={"sub": str(user_id), "username": user.username}
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/login", response_model=Token)
def login(user: UserLogin):
    """Login and get access token"""
    # Authenticate user
    authenticated_user = auth.authenticate_user(user.username, user.password)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = auth.create_access_token(
        data={"sub": str(authenticated_user["id"]), "username": authenticated_user["username"]}
    )

    return {"access_token": access_token, "token_type": "bearer"}


# ============================================
# PROTECTED ENDPOINTS - USER
# ============================================

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(auth.get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        created_at=current_user["created_at"]
    )


# ============================================
# PROTECTED ENDPOINTS - BOOKMARKS
# ============================================

@app.post("/bookmarks/add", response_model=BookmarkResponse)
async def add_bookmark(
    bookmark: BookmarkCreate,
    current_user: dict = Depends(auth.get_current_user)
):
    """Add a new bookmark"""
    # Validate URL format
    if not (bookmark.url.startswith("http://") or bookmark.url.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http:// or https://"
        )

    # Create bookmark
    bookmark_id = db.create_bookmark(
        user_id=current_user["id"],
        url=bookmark.url,
        description=bookmark.description,
        tags=bookmark.tags,
        category=bookmark.category,
        source=None
    )

    # Get created bookmark
    created_bookmark = db.get_bookmark_by_id(bookmark_id, current_user["id"])

    return BookmarkResponse(**created_bookmark)


@app.get("/bookmarks/list")
async def list_bookmarks(current_user: dict = Depends(auth.get_current_user)):
    """List all user's bookmarks"""
    bookmarks = db.get_user_bookmarks(current_user["id"])
    return {"bookmarks": [BookmarkResponse(**b) for b in bookmarks]}


@app.get("/search")
async def search_bookmarks(
    keyword: Optional[str] = Query(None, description="Search keyword"),
    current_user: Optional[dict] = Depends(auth.get_current_user_optional)
):
    """
    Search bookmarks:
    - If authenticated: search user's own bookmarks
    - If anonymous: search all public bookmarks
    """
    if current_user:
        # Authenticated user - search their own bookmarks
        bookmarks = db.search_user_bookmarks(current_user["id"], keyword)
    else:
        # Anonymous user - search public bookmarks from all users
        bookmarks = db.search_public_bookmarks(keyword)

    # Format results to match frontend expectations
    results = [{
        "url": b["url"],
        "description": b["description"],
        "tags": b["tags"],
        "category": b["category"],
        "source": b.get("source"),
        "username": b.get("username")  # Include username for public search results
    } for b in bookmarks]

    return {"results": results}


@app.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: int,
    current_user: dict = Depends(auth.get_current_user)
):
    """Delete a bookmark"""
    success = db.delete_bookmark(bookmark_id, current_user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found"
        )

    return {"message": "Bookmark deleted successfully"}


# ============================================
# PROTECTED ENDPOINTS - REPOSITORIES
# ============================================

@app.post("/repositories/add", response_model=RepositoryImportResult)
async def add_repository(
    repository: RepositoryCreate,
    current_user: dict = Depends(auth.get_current_user)
):
    """Add a repository and import its bookmarks"""
    # Validate URL format
    if not (repository.url.startswith("http://") or repository.url.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http:// or https://"
        )

    # Fetch JSON from URL
    try:
        response = requests.get(repository.url, timeout=10)
        response.raise_for_status()
        bookmarks_data = response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch repository: {str(e)}"
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format in repository"
        )

    # Validate JSON format (should be array of bookmarks)
    if not isinstance(bookmarks_data, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository must contain an array of bookmarks"
        )

    # Create repository
    repository_id = db.create_repository(
        user_id=current_user["id"],
        name=repository.name,
        url=repository.url
    )

    # Import bookmarks
    imported_count = 0
    for item in bookmarks_data:
        try:
            url = item.get("url", "")
            description = item.get("description", "")
            tags = item.get("tags", [])
            category = item.get("category", "IMPORTED")

            if url and description:
                db.create_bookmark(
                    user_id=current_user["id"],
                    url=url,
                    description=description,
                    tags=tags if isinstance(tags, list) else [],
                    category=category,
                    source=repository.name
                )
                imported_count += 1
        except Exception as e:
            # Continue importing other bookmarks if one fails
            print(f"Failed to import bookmark: {e}")
            continue

    # Update sync time
    db.update_repository_sync_time(repository_id)

    return RepositoryImportResult(
        repository_id=repository_id,
        bookmarks_imported=imported_count,
        message=f"Successfully imported {imported_count} bookmarks from {repository.name}"
    )


@app.get("/repositories/list")
async def list_repositories(current_user: dict = Depends(auth.get_current_user)):
    """List all user's repositories"""
    repositories = db.get_user_repositories(current_user["id"])
    return {"repositories": [RepositoryResponse(**r) for r in repositories]}


@app.post("/repositories/{repository_id}/sync", response_model=RepositoryImportResult)
async def sync_repository(
    repository_id: int,
    current_user: dict = Depends(auth.get_current_user)
):
    """Re-sync/re-import bookmarks from a repository"""
    # Get repository
    repository = db.get_repository_by_id(repository_id, current_user["id"])
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )

    # Delete existing bookmarks from this repository
    db.delete_bookmarks_by_source(current_user["id"], repository["name"])

    # Fetch JSON from URL
    try:
        response = requests.get(repository["url"], timeout=10)
        response.raise_for_status()
        bookmarks_data = response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch repository: {str(e)}"
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format in repository"
        )

    # Import bookmarks
    imported_count = 0
    for item in bookmarks_data:
        try:
            url = item.get("url", "")
            description = item.get("description", "")
            tags = item.get("tags", [])
            category = item.get("category", "IMPORTED")

            if url and description:
                db.create_bookmark(
                    user_id=current_user["id"],
                    url=url,
                    description=description,
                    tags=tags if isinstance(tags, list) else [],
                    category=category,
                    source=repository["name"]
                )
                imported_count += 1
        except Exception as e:
            print(f"Failed to import bookmark: {e}")
            continue

    # Update sync time
    db.update_repository_sync_time(repository_id)

    return RepositoryImportResult(
        repository_id=repository_id,
        bookmarks_imported=imported_count,
        message=f"Successfully synced {imported_count} bookmarks from {repository['name']}"
    )


@app.delete("/repositories/{repository_id}")
async def delete_repository(
    repository_id: int,
    current_user: dict = Depends(auth.get_current_user)
):
    """Delete a repository and all its bookmarks"""
    success = db.delete_repository(repository_id, current_user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )

    return {"message": "Repository and associated bookmarks deleted successfully"}


# ============================================
# PUBLIC ENDPOINTS - USER PROFILES
# ============================================

@app.get("/users/{username}")
async def get_public_profile(username: str):
    """Get public user profile with repositories and bookmarks"""
    user = db.get_public_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    repositories = db.get_user_public_repositories(user["id"])
    bookmarks = db.get_user_public_bookmarks(user["id"])

    return {
        "user": user,
        "repositories": repositories,
        "bookmarks": bookmarks,
        "stats": {
            "total_repositories": len(repositories),
            "total_bookmarks": len(bookmarks)
        }
    }


@app.get("/users")
async def list_public_users():
    """List all users with public content"""
    users = db.get_users_with_public_content()
    return {"users": users}
