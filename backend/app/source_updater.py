"""Only this component applies approved DAG bytes. No client paths are accepted."""
import os
import tempfile
from pathlib import Path

from backend.app.change_models import SourceRemediation, SourceRemediationState
from backend.app.source_validation import source_hash
from backend.app.source_review_validation import resolve_review_source
from backend.app.source_execution_policy import check_record_policy


class StaleSourceError(ValueError):
    pass


def read_exact(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".reviewed-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class DagSourceUpdater:
    def __init__(self, backup_root: Path):
        self.backup_root = backup_root

    def check(self, record: SourceRemediation) -> Path:
        source = record.change.source_code
        if source is None or source.file_path != f"dags/{record.dag_id}.py":
            raise ValueError("Unexpected source target.")
        path = resolve_review_source(record.dag_id)
        if source_hash(read_exact(path)) != record.base_source_hash:
            raise StaleSourceError("The DAG source changed after this proposal was created. Re-run Change Review.")
        if source_hash(source.before_code) != record.base_source_hash:
            raise ValueError("Base source fingerprint does not match the audit record.")
        if record.change.target != record.dag_id:
            raise ValueError("Unexpected source function or change target.")
        check_record_policy(record)
        digest = source_hash(source.proposed_code)
        validation, approval = record.validation, record.approval
        if not validation or not validation.valid or not approval:
            raise ValueError("Valid review and explicit human approval are required.")
        if not (record.revision == validation.revision == approval.revision
                and digest == record.proposal_hash == validation.source_hash == approval.source_hash):
            raise ValueError("Validation and approval must match the exact reviewed revision/hash.")
        return path

    def backup(self, record: SourceRemediation) -> Path:
        path = self.check(record)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        # UUID comes from the server record, never a user-supplied pathname.
        from uuid import UUID
        name = str(UUID(record.proposal_id))
        backup = self.backup_root / f"{name}-r{record.revision}.bak"
        with backup.open("xb") as handle:
            handle.write(path.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        if source_hash(read_exact(backup)) != record.base_source_hash:
            raise StaleSourceError("Source changed while taking the backup; application blocked.")
        return backup

    def apply(self, record: SourceRemediation) -> None:
        if record.state != SourceRemediationState.APPLYING or not record.backup_path:
            raise ValueError("Application requires the applying state and a persisted backup.")
        path = self.check(record)
        backup = Path(record.backup_path)
        if backup.parent.resolve() != self.backup_root.resolve() or source_hash(read_exact(backup)) != record.base_source_hash:
            raise ValueError("A valid original backup is required.")
        atomic_write(path, record.change.source_code.proposed_code.encode("utf-8"))

    def rollback(self, record: SourceRemediation) -> None:
        path = resolve_review_source(record.dag_id)
        if source_hash(read_exact(path)) != record.proposal_hash:
            raise StaleSourceError("Rollback blocked: source changed externally after application.")
        backup = Path(record.backup_path)
        if backup.parent.resolve() != self.backup_root.resolve() or source_hash(read_exact(backup)) != record.base_source_hash:
            raise ValueError("Backup is missing or its fingerprint changed.")
        atomic_write(path, backup.read_bytes())
