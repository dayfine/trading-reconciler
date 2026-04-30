from reconciler.sexp import encode


def test_none_is_unit():
    assert encode(None) == "()"


def test_bool_atoms():
    assert encode(True) == "true"
    assert encode(False) == "false"


def test_int_and_float():
    assert encode(42) == "42"
    assert encode(3.14) == "3.14"


def test_atom_unquoted_when_safe():
    assert encode("AAPL") == "AAPL"
    assert encode("LONG") == "LONG"
    assert encode("2024-01-02") == "2024-01-02"


def test_atom_quoted_when_has_spaces():
    assert encode("hello world") == '"hello world"'


def test_empty_string_quoted():
    assert encode("") == '""'


def test_quote_escapes_quotes():
    assert encode('a"b') == '"a\\"b"'


def test_dict_emits_alist():
    assert encode({"a": 1, "b": 2}) == "((a 1) (b 2))"


def test_list_emits_paren_seq():
    assert encode([1, 2, 3]) == "(1 2 3)"


def test_nested_structure():
    payload = {"summary": {"x": 1}, "items": [{"a": 1}, {"a": 2}]}
    assert encode(payload) == "((summary ((x 1))) (items (((a 1)) ((a 2)))))"


def test_null_field_in_dict():
    assert encode({"unrealized": None}) == "((unrealized ()))"
