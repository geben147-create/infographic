"""Test fixtures — skeletal scaffold. Plan 01-04 fills in full implementations."""
import pytest
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def db_session():
    """In-memory SQLite session for testing."""
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def tmp_pipeline_dir(tmp_path):
    """Temporary directory for pipeline artifact tests."""
    return str(tmp_path)
