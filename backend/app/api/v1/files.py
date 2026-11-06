"""File upload + signed-URL download routes."""

import uuid

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from fastapi import (
    File as FastFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.file import File, FileVisibility
from app.models.user import User, UserRole
from app.schemas.file import FileOut, SignedUrlOut
from app.services import storage_service

router = APIRouter(prefix="/files", tags=["files"])

SIGNED_URL_TTL_SECONDS = 300
PROFILE_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
CREATOR_PORTFOLIO_MIME_TYPES = frozenset(
    {
        *PROFILE_IMAGE_MIME_TYPES,
        "video/mp4",
        "video/quicktime",
        "application/pdf",
    }
)


async def _save_public_profile_file(
    *,
    file: UploadFile,
    content_length: int | None,
    user: User,
    db: AsyncSession,
    allowed_mime_types: frozenset[str],
) -> FileOut:
    if user.role not in {UserRole.creator, UserRole.brand}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator and brand accounts can upload profile files.",
        )
    file_row = await storage_service.save_upload(
        db,
        user=user,
        upload_file=file,
        content_length=content_length,
        visibility=FileVisibility.public,
        allowed_mime_types=allowed_mime_types,
    )
    await db.commit()
    return FileOut.model_validate(file_row)


@router.post("", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = FastFile(...),
    content_length: int | None = Header(default=None, alias="Content-Length"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    file_row = await storage_service.save_upload(
        db,
        user=user,
        upload_file=file,
        content_length=content_length,
        visibility=FileVisibility.private,
    )
    await db.commit()
    return FileOut.model_validate(file_row)


@router.post("/profile-image", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_profile_image(
    file: UploadFile = FastFile(...),
    content_length: int | None = Header(default=None, alias="Content-Length"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    return await _save_public_profile_file(
        file=file,
        content_length=content_length,
        user=user,
        db=db,
        allowed_mime_types=PROFILE_IMAGE_MIME_TYPES,
    )


@router.post(
    "/creator-portfolio",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_creator_portfolio_file(
    file: UploadFile = FastFile(...),
    content_length: int | None = Header(default=None, alias="Content-Length"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    if user.role != UserRole.creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator accounts can upload portfolio files.",
        )
    return await _save_public_profile_file(
        file=file,
        content_length=content_length,
        user=user,
        db=db,
        allowed_mime_types=CREATOR_PORTFOLIO_MIME_TYPES,
    )


@router.get("/public/{file_id}")
async def get_public_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    file_row = await db.get(File, file_id)
    if (
        file_row is None
        or file_row.visibility != FileVisibility.public
        or file_row.content_type not in PROFILE_IMAGE_MIME_TYPES | CREATOR_PORTFOLIO_MIME_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )

    def _iter_stream():
        with storage_service.open_file_stream(file_row) as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        _iter_stream(),
        media_type=file_row.content_type,
        headers={
            "Content-Disposition": "inline",
            "Content-Length": str(file_row.size_bytes),
            "Cache-Control": "public, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{file_id}/signed-url", response_model=SignedUrlOut)
async def issue_signed_url(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SignedUrlOut:
    file_row = await db.get(File, file_id)
    if file_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )
    if (
        file_row.visibility == FileVisibility.private
        and file_row.owner_user_id != user.id
        and user.role != UserRole.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot request a URL for this file.",
        )
    token = storage_service.issue_signed_file_token(
        file_id=file_row.id,
        user_id=user.id,
        ttl_seconds=SIGNED_URL_TTL_SECONDS,
    )
    return SignedUrlOut(
        url=f"/api/v1/files/signed/{token}",
        expires_in=SIGNED_URL_TTL_SECONDS,
    )


@router.get("/signed/{token}")
async def stream_signed_file(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    file_row, token_user_id = await storage_service.resolve_signed_file_token(
        db,
        token=token,
    )

    # Private files require the token subject to match the viewer (or admin).
    if file_row.visibility == FileVisibility.private:
        if token_user_id != user.id and user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This token is not valid for the current viewer.",
            )

    def _iter_stream():
        with storage_service.open_file_stream(file_row) as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        _iter_stream(),
        media_type=file_row.content_type,
        headers={
            "Content-Disposition": (f'attachment; filename="{file_row.original_filename}"'),
            "Content-Length": str(file_row.size_bytes),
        },
    )
