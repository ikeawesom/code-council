"""notifications API routes - the fan-out list a user reads on login."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Document, Edit, Notification, Task, User

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

SessionDep = Annotated[Session, Depends(get_session)]


def _notification_payload(session: Session, notification: Notification) -> dict:
    actor = None
    if notification.edit_id is not None:
        edit = session.get(Edit, notification.edit_id)
        if edit is not None and edit.user_id is not None:
            user = session.get(User, edit.user_id)
            if user is not None:
                actor = {"name": user.name, "initials": user.initials}

    task_reference = None
    if notification.task_id is not None:
        task = session.get(Task, notification.task_id)
        task_reference = task.reference if task else None

    document_slug = None
    if notification.document_id is not None:
        document = session.get(Document, notification.document_id)
        document_slug = document.slug if document else None

    return {
        "id": notification.id,
        "message": notification.message,
        "read": notification.read,
        "created_at": notification.created_at.isoformat(),
        "actor": actor,
        "task_id": notification.task_id,
        "task_reference": task_reference,
        "document_slug": document_slug,
    }


@router.get("")
def list_notifications(session: SessionDep, user_id: int) -> dict:
    """One user's notifications, newest first, plus the unread count."""
    notifications = session.exec(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    ).all()
    unread = sum(1 for n in notifications if not n.read)
    return {
        "unread": unread,
        "notifications": [_notification_payload(session, n) for n in notifications],
    }


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: int, session: SessionDep) -> dict:
    """Mark one notification read."""
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail=f"no notification with id {notification_id}")
    notification.read = True
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return _notification_payload(session, notification)
