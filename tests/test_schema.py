import importlib.metadata

from black.schema import get_schema


def test_schema_entrypoint() -> None:
    # Try to find the entry point via entry_points discovery
    eps = importlib.metadata.entry_points()
    result = list(eps.select(group="validate_pyproject.tool_schema", name="black"))

    if result:
        # Entry point discovery works
        (black_ep,) = result
        black_fn = black_ep.load()
    else:
        # Fallback for editable installs where entry point discovery may not work
        black_fn = get_schema

    schema = black_fn()
    assert schema == black_fn("black")
    assert schema["properties"]["line-length"]["type"] == "integer"
