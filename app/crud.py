"""REST API for the two marketplace interfaces.

Provider dashboard (frontend/) uses the CRUD endpoints; buyer agents use
GET /catalog + POST /sessions/{id}/book. Paths and JSON field names match
HANDOVER §4 exactly so the frontend needs zero mapping.
"""
from fastapi import APIRouter, Depends, HTTPException

from app import store
from app.models import Experience, Session

router = APIRouter()


def _client():
    # late import so this module stays import-safe without a DB
    from app.main import _client as get_cached_client
    client = get_cached_client()
    store.ensure_tables(client)
    return client


# --- experiences (provider CRUD) ---

@router.get("/experiences")
def list_experiences(client=Depends(_client)) -> list[Experience]:
    return store.list_experiences(client)


@router.post("/experiences")
def create_experience(exp: Experience, client=Depends(_client)) -> Experience:
    return store.upsert_experience(client, exp)


@router.put("/experiences/{exp_id}")
def update_experience(exp_id: str, exp: Experience, client=Depends(_client)) -> Experience:
    exp.id = exp_id
    return store.upsert_experience(client, exp)


@router.delete("/experiences/{exp_id}")
def delete_experience(exp_id: str, client=Depends(_client)) -> dict:
    store.delete_experience(client, exp_id)
    return {"ok": True}


# --- sessions (provider CRUD) ---

@router.get("/sessions")
def list_sessions(client=Depends(_client)) -> list[Session]:
    return store.list_sessions(client)


@router.post("/sessions")
def create_session(ses: Session, client=Depends(_client)) -> Session:
    return store.upsert_session(client, ses)


@router.put("/sessions/{session_id}")
def update_session(session_id: str, ses: Session, client=Depends(_client)) -> Session:
    ses.id = session_id
    return store.upsert_session(client, ses)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, client=Depends(_client)) -> dict:
    store.delete_session(client, session_id)
    return {"ok": True}


# --- agent-facing booking interface ---

@router.get("/catalog")
def catalog(client=Depends(_client)) -> list[dict]:
    """What a buyer agent sees: published experiences with their open sessions."""
    experiences = [e for e in store.list_experiences(client) if e.status == "published"]
    sessions = store.list_sessions(client)
    return [
        {
            **exp.model_dump(),
            "openSessions": [
                s.model_dump() for s in sessions
                if s.experienceId == exp.id and s.status == "open"
            ],
        }
        for exp in experiences
    ]


@router.post("/sessions/{session_id}/book")
def book(session_id: str, client=Depends(_client)) -> Session:
    ses, err = store.book_session(client, session_id)
    if err == "not_found":
        raise HTTPException(status_code=404, detail="session not found")
    if err == "already_booked":
        raise HTTPException(status_code=409, detail="session already booked")
    return ses
