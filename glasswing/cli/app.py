"""Typer CLI — the primary operator interface (GLASSWING_SPEC.md section
2.1: "The CLI is what Sonnet tests against and what the acceptance
criteria use.").

Schema is owned by Alembic (alembic.ini / glasswing/storage/migrations/) —
run `alembic upgrade head` before using any command here.
"""

from __future__ import annotations

import os
import uuid

import typer
from sqlalchemy.orm import Session, sessionmaker

from glasswing.services import audit
from glasswing.storage.database import make_engine, make_session_factory, session_scope
from glasswing.storage.models import EngagementRow

app = typer.Typer(help="Glasswing Governance OS operator CLI.")
engagement_app = typer.Typer(help="Manage engagements.")
audit_app = typer.Typer(help="Inspect and verify audit chains.")
app.add_typer(engagement_app, name="engagement")
app.add_typer(audit_app, name="audit")


def _db_url() -> str:
    return os.environ.get("GLASSWING_DB_URL", "sqlite:///glasswing.db")


def _session_factory() -> sessionmaker[Session]:
    engine = make_engine(_db_url())
    return make_session_factory(engine)


@engagement_app.command("new")
def engagement_new(
    client: str = typer.Option(..., "--client", help="Client name."),
    sector: str = typer.Option(..., "--sector", help="Client sector."),
    jurisdictions: str = typer.Option(
        ...,
        "--jurisdictions",
        help="Comma-separated jurisdictions, e.g. US-CO,EU.",
    ),
) -> None:
    """Creates a new engagement and writes its genesis audit entry."""
    jurisdiction_list = [j.strip() for j in jurisdictions.split(",") if j.strip()]
    if not jurisdiction_list:
        typer.echo("At least one jurisdiction is required.", err=True)
        raise typer.Exit(code=1)

    session_factory = _session_factory()
    with session_scope(session_factory) as session:
        engagement = EngagementRow(
            client_name=client,
            sector=sector,
            jurisdictions=jurisdiction_list,
            data_dir="",
        )
        session.add(engagement)
        session.flush()  # assigns engagement.id
        engagement.data_dir = f"data/engagements/{engagement.id}"

        audit.append_genesis(
            session,
            engagement_id=engagement.id,
            payload={
                "client_name": client,
                "sector": sector,
                "jurisdictions": jurisdiction_list,
            },
        )
        engagement_id = engagement.id

    typer.echo(str(engagement_id))


@audit_app.command("verify")
def audit_verify(
    engagement: str = typer.Option(..., "--engagement", help="Engagement id."),
) -> None:
    """Verifies the tamper-evident hash chain for an engagement.

    Exits 0 if the chain verifies, 1 otherwise.
    """
    try:
        engagement_id = uuid.UUID(engagement)
    except ValueError as exc:
        typer.echo(f"Invalid engagement id: {engagement}", err=True)
        raise typer.Exit(code=1) from exc

    session_factory = _session_factory()
    with session_scope(session_factory) as session:
        result = audit.verify_chain(session, engagement_id)

    typer.echo(result.message)
    if not result.valid:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
