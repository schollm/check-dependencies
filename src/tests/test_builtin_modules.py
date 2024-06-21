from check_dependencies.builtin_module import BUILTINS


def test_is_set():
    assert isinstance(BUILTINS, set)


def test_contains_future():
    assert "__future__" in BUILTINS


def test_no_empty_module():
    assert "" not in BUILTINS


def test_all_correct_names():
    for module in BUILTINS:
        assert module.isidentifier()
