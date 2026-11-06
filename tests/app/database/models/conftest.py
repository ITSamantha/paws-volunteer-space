from collections.abc import Callable
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table

from app.database.models import Base

TableOf = Callable[[type[Base]], Table]
CheckNames = Callable[[type[Base]], set[str]]


@pytest.fixture
def table_of() -> TableOf:
    def get_table(model: type[Base]) -> Table:
        return cast(Table, model.__table__)

    return get_table


@pytest.fixture
def check_names(table_of: TableOf) -> CheckNames:
    def get_names(model: type[Base]) -> set[str]:
        return {
            str(constraint.name)
            for constraint in table_of(model).constraints
            if isinstance(constraint, CheckConstraint)
        }

    return get_names
