import pytest
from capsule_brain.security.input_sanitizer import sanitize_input, validate_tool_params


def test_sanitize_basic_removes_dangerous_chars_and_trims():
    s = '  <script>alert("x")</script>  '
    cleaned = sanitize_input(s)
    assert '<' not in cleaned and '>' not in cleaned and '"' not in cleaned and "'" not in cleaned
    assert cleaned == 'scriptalertxscript'


def test_sanitize_collapse_whitespace_and_limit_length():
    long = 'a' * 2500
    cleaned = sanitize_input(long)
    assert len(cleaned) == 2000
    spaced = sanitize_input('hello\n\n   world\t!')
    assert spaced == 'hello world !'


def test_validate_tool_params_mixed_types():
    params = {
        'name': '  ">rm -rf"  ',
        'count': 5,
        'flag': True,
        'tags': ['x<y', 'hello']
    }
    out = validate_tool_params(params)
    assert out['name'] == 'rm -rf'
    assert out['count'] == 5
    assert out['flag'] is True
    assert out['tags'] == ['xy', 'hello']