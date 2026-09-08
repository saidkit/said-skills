from src.parse import parse

def test_parse():
    assert parse("a=1")["a"] == "1"
