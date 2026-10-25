import pytest

from ordo.sectors import setup_b2b_sales
from ordo.store import Store


@pytest.fixture
def store():
    """B2B satış tipləri qeydiyyatdan keçmiş boş Store."""
    s = Store()
    setup_b2b_sales(s)
    return s
