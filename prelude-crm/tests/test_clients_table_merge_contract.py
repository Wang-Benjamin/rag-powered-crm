"""Static contracts for the direct clients table merge cutover.

These tests intentionally avoid live DB access and Alembic execution. They guard
against post-cutover UndefinedTable failures by ensuring runtime code no longer
references the legacy split tables.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOTS = [
    REPO_ROOT / "prelude",
    REPO_ROOT / ".claude" / "skills" / "seed-demo-data",
    REPO_ROOT / "scripts" / "yuhua-lighting-demo-seed.sql",
]
INTENTIONAL_LEGACY_FILES = {
    REPO_ROOT / "scripts" / "merge-clients-direct-cutover.sql",
    REPO_ROOT / "scripts" / "restore-clients-info-details-template.sql",
}


def _runtime_files() -> list[Path]:
    files: list[Path] = []
    for root in RUNTIME_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".sql", ".md", ".ts", ".tsx", ".js"}:
                if path in INTENTIONAL_LEGACY_FILES or path == Path(__file__).resolve():
                    continue
                files.append(path)
    return files


def test_runtime_code_no_longer_references_legacy_client_tables() -> None:
    offenders: list[str] = []
    for path in _runtime_files():
        text = path.read_text(errors="ignore")
        info = "clients" + "_info"
        details = "clients" + "_details"
        legacy_table_tokens = [
            f"__tablename__ = '{info}'",
            f"__tablename__ = '{details}'",
            f"public.{info}.client_id",
            f"FROM {info}",
            f"JOIN {details}",
            f"UPDATE {details}",
            f"INSERT INTO {details}",
            f"DELETE FROM {details}",
        ]
        if any(token in text for token in legacy_table_tokens):
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []


def test_user_settings_model_matches_direct_cutover_shape() -> None:
    text = (REPO_ROOT / "prelude" / "prelude-user-settings" / "alembic_postgres" / "models.py").read_text()

    assert "class Clients(Base):" in text
    assert "__tablename__ = 'clients'" in text
    assert "class ClientsInfo" not in text
    assert "class ClientsDetails" not in text

    for field in ["health_score", "status", "stage", "signal", "trade_intel"]:
        assert field in text

    assert "location: Mapped[Optional[str]] = mapped_column(String(255))" in text

    assert "public." + "clients" + "_info.client_id" not in text
    assert "public.clients.client_id" in text

    # The direct DB script renames clients_info to clients, so PostgreSQL keeps
    # the existing sequence/PK names. models.py must mirror that live shape.
    assert "clients_info_client_id_seq" in text
    assert "clients_info_pkey" in text
    assert "clients_client_id_seq" not in text
    assert "clients_pkey" not in text


def test_direct_cutover_script_does_not_advance_alembic() -> None:
    text = (REPO_ROOT / "scripts" / "merge-clients-direct-cutover.sql").read_text()

    assert "ALTER TABLE public.clients_info" in text
    assert "DROP TABLE public.clients_details" in text
    assert "ALTER TABLE public.clients_info RENAME TO clients" in text
    lowered = text.lower()
    assert "update alembic_version" not in lowered
    assert "insert into alembic_version" not in lowered
    assert "alembic upgrade" not in lowered


def test_cleanup_does_not_reintroduce_split_table_helpers() -> None:
    leadgen_repo = (
        REPO_ROOT
        / "prelude"
        / "prelude-leadgen"
        / "data"
        / "repositories"
        / "crm_repository.py"
    ).read_text()
    crm_router = (
        REPO_ROOT / "prelude" / "prelude-crm" / "routers" / "crm_data_router.py"
    ).read_text()

    assert "transfer_lead_emails_to_interactions" not in leadgen_repo
    assert "FROM lead_emails" not in leadgen_repo
    assert "json.dumps(trade_intel_value)" not in leadgen_repo
    assert "info_updates" not in crm_router
    assert "details_updates" not in crm_router
