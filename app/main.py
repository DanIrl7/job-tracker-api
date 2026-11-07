import datetime as dt
import os

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, make_engine, make_session_factory
from app.models import Application, User
from app.schemas import (
    ApplicationIn,
    ApplicationOut,
    ApplicationPatch,
    LoginIn,
    RegisterIn,
    Status,
    TokenOut,
    UserOut,
)
from app.security import create_token, decode_token, hash_password, verify_password

ACTIVE_STATUSES = ("applied", "interviewing")
NON_NULLABLE_FIELDS = ("company", "role_title", "status", "applied_on")


def create_app(database_url: str | None = None, secret_key: str | None = None) -> FastAPI:
    """Build the app. Settings come from arguments first, then from environment variables.

    Run it with: uvicorn app.main:create_app --factory
    """
    url = database_url or os.environ.get("DATABASE_URL", "sqlite:///./tracker.db")
    secret = secret_key or os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY must be set")

    engine = make_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)

    app = FastAPI(title="Job Tracker API", version="1.0.0")
    app.state.engine = engine

    bearer = HTTPBearer(auto_error=False)

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def current_user(
        creds: HTTPAuthorizationCredentials | None = Depends(bearer),
        db: Session = Depends(get_db),
    ) -> User:
        if creds is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        user_id = decode_token(creds.credentials, secret)
        user = db.get(User, user_id) if user_id is not None else None
        if user is None:
            raise HTTPException(status_code=401, detail="invalid or expired token")
        return user

    def owned_application(db: Session, user: User, application_id: int) -> Application:
        app_row = db.scalar(
            select(Application).where(
                Application.id == application_id, Application.user_id == user.id
            )
        )
        if app_row is None:
            # Same response whether the id is missing or belongs to someone else.
            raise HTTPException(status_code=404, detail="application not found")
        return app_row

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.post("/auth/register", response_model=UserOut, status_code=201)
    def register(body: RegisterIn, db: Session = Depends(get_db)) -> User:
        email = body.email.lower()
        if db.scalar(select(User).where(User.email == email)) is not None:
            raise HTTPException(status_code=409, detail="email already registered")
        user = User(email=email, password_hash=hash_password(body.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @app.post("/auth/login", response_model=TokenOut)
    def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
        user = db.scalar(select(User).where(User.email == body.email.lower()))
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid email or password")
        return TokenOut(access_token=create_token(user.id, secret))

    @app.post("/applications", response_model=ApplicationOut, status_code=201)
    def create_application(
        body: ApplicationIn,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> Application:
        row = Application(user_id=user.id, **body.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @app.get("/applications", response_model=list[ApplicationOut])
    def list_applications(
        status: Status | None = None,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> list[Application]:
        query = select(Application).where(Application.user_id == user.id)
        if status is not None:
            query = query.where(Application.status == status)
        return list(db.scalars(query.order_by(Application.applied_on.desc(), Application.id)))

    # Declared before /applications/{application_id} so "follow-ups" is not read as an id.
    @app.get("/applications/follow-ups", response_model=list[ApplicationOut])
    def follow_ups(
        days: int = Query(default=7, ge=0, le=90),
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> list[Application]:
        today = dt.date.today()
        query = (
            select(Application)
            .where(
                Application.user_id == user.id,
                Application.status.in_(ACTIVE_STATUSES),
                Application.follow_up_on >= today,
                Application.follow_up_on <= today + dt.timedelta(days=days),
            )
            .order_by(Application.follow_up_on, Application.id)
        )
        return list(db.scalars(query))

    @app.get("/applications/{application_id}", response_model=ApplicationOut)
    def get_application(
        application_id: int,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> Application:
        return owned_application(db, user, application_id)

    @app.patch("/applications/{application_id}", response_model=ApplicationOut)
    def update_application(
        application_id: int,
        body: ApplicationPatch,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> Application:
        row = owned_application(db, user, application_id)
        changes = body.model_dump(exclude_unset=True)
        for field in NON_NULLABLE_FIELDS:
            if field in changes and changes[field] is None:
                raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        for field, value in changes.items():
            setattr(row, field, value)
        db.commit()
        db.refresh(row)
        return row

    @app.delete("/applications/{application_id}", status_code=204)
    def delete_application(
        application_id: int,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> Response:
        row = owned_application(db, user, application_id)
        db.delete(row)
        db.commit()
        return Response(status_code=204)

    return app
