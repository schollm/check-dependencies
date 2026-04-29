"""Tests for the lib module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from check_dependencies.app_config import AppConfig
from check_dependencies.lib import Dependency, Module, Package, Packages, _canonical


class TestModule:
    """Test suite for the Module."""

    def test__lt__(self) -> None:
        """Test comparison."""
        assert Module("a") < Module("x")
        assert Module("x", raw=False) < Module("a", raw=True)
        assert Module("a", raw=True) < Module("x", raw=True)

    def test__lt___notimplemented(self) -> None:
        """Test comparison against non-Module returns NotImplemented."""
        assert Module("foo").__lt__(0) is NotImplemented

    def test__eq__(self) -> None:
        """Test equality."""
        assert Module("foo") == Module("foo")
        assert Module("foo", raw=False) == Module("foo", raw=False)
        assert Module("foo", raw=True) == Module("foo", raw=True)
        assert Module("foo") != Module("foo", raw=True)
        assert Module("foo").__eq__(0) is NotImplemented

    @pytest.mark.parametrize(
        "module, expected",
        [
            (Module("foo"), "Module('foo')"),
            (Module("foo", raw=False), "Module('foo')"),
            (Module("foo", raw=True), "Module('foo', raw=True)"),
        ],
    )
    def test__repr__(self, module: Module, expected: str) -> None:
        """Test __repr__."""
        assert repr(module) == expected

    @pytest.mark.parametrize(
        "module, expected",
        [
            (Module("numpy.linalg").main, Module("numpy")),
            (Module("sklearn").main, Module("sklearn")),
            (Module("PIL.Image").main, Module("PIL")),
            (Module("foo.bar.baz", raw=True).main, Module("foo.bar.baz", raw=True)),
        ],
    )
    def test_main(self, module: Module, expected: Module) -> None:
        """Test the main property."""
        assert module.main == expected


class TestPackage:
    """Test suite for the Package value object."""

    @pytest.mark.parametrize(
        "left,right",
        [
            ("PyJWT", "pyjwt"),
            ("scikit-learn", "scikit_learn"),
            ("SciKit-Learn>=1.0", "scikit_learn"),
            ("Scikit-Learn>=1", "scikit-Learn==*"),
        ],
    )
    def test_equal_packages_share_canonical_and_hash(
        self, left: str, right: str
    ) -> None:
        """Equivalent package spellings compare and hash equally."""
        a = Package(left)
        b = Package(right)

        assert a == b
        assert a.canonical == b.canonical
        assert hash(a) == hash(b)

    @pytest.mark.parametrize(
        "left,right",
        [
            ("pytest", "pyyaml"),
            ("requests", "requestx"),
        ],
    )
    def test_different_packages_are_not_equal(self, left: str, right: str) -> None:
        """Different package names should not compare as equal."""
        assert Package(left) != Package(right)

    @pytest.mark.parametrize(
        "value,other",
        [
            ("PyJWT", "pyjwt"),
            ("scikit-learn", "scikit_learn"),
        ],
    )
    def test_package_equals_matching_string(self, value: str, other: str) -> None:
        """Package equality also works against canonical-equivalent strings."""
        assert Package(value) == other

    @pytest.mark.parametrize(
        "raw,expected_str,expected_bool",
        [
            ("PyJWT", "PyJWT", True),
            ("  ", "", False),
            ("", "", False),
        ],
    )
    def test_string_and_bool_behavior(
        self, raw: str, expected_str: str, expected_bool: bool
    ) -> None:
        """Original name is kept for display while truthiness uses canonical name."""
        package = Package(raw)
        assert str(package) == expected_str
        assert bool(package) is expected_bool

    def test_eq_not_implemented(self) -> None:
        """Test that we return NotImplemented for unknown comparison."""
        assert Package("foo").__eq__(0) is NotImplemented

    def test_gt_not_implemented(self) -> None:
        """Test that we return NotImplemented for unknown comparison."""
        assert Package("foo").__gt__(0) is NotImplemented

    def test_cmp_str(self) -> None:
        """Test comparison against a string."""
        assert Package("a==1.0.0") < "b"

    @pytest.mark.parametrize(
        "requirement, expected_module",
        [
            ("foo > 0", "foo"),
            ("scikit-learn", "scikit_learn"),
            ("SciKit-Learn >= 1.0", "scikit_learn"),
        ],
    )
    def test_modules_fallback_uses_canonical_name(
        self, requirement: str, expected_module: str
    ) -> None:
        """Fallback for unmapped packages should be a canonical module name."""
        packages = Packages([])  # no explicit mapping -> fallback path
        assert packages.modules(Package(requirement)) == {Module(expected_module)}

    def test___repr__(self) -> None:
        """Test __repr__."""
        assert repr(Package("foo")) == "Package('foo')"


class TestPackages:
    """Test suite for the Packages class, which manages package-module mappings."""

    def test_packages_multi_module_and_multi_package_mapping(self) -> None:
        """Packages supports many-to-many mappings.

        - one package can provide multiple modules
        - one module can be provided by multiple packages
        """
        pkg_a, pkg_b, pkg_c = (Package(f"pkg_{x}") for x in "abc")
        mod_common = Module("mod_common")
        mod_a_only = Module("mod_a_only")
        mod_b_only = Module("mod_b_only")
        mod_c_only = Module("mod_c_only")
        packages = Packages(
            [
                (pkg_a, mod_common),
                (pkg_a, mod_a_only),
                (pkg_b, mod_common),
                (pkg_b, mod_b_only),
                (pkg_c, mod_c_only),
            ]
        )

        # package -> modules (one package provides multiple modules)
        assert packages.modules(pkg_a) == {mod_common, mod_a_only}
        assert packages.modules(pkg_b) == {mod_common, mod_b_only}
        assert packages.modules(pkg_c) == {mod_c_only}

        # module -> packages (one module provided by multiple packages)
        assert packages.packages(mod_common) == {pkg_a, pkg_b}
        assert packages.packages(mod_a_only) == {pkg_a}
        assert packages.packages(mod_b_only) == {pkg_b}
        assert packages.packages(mod_c_only) == {pkg_c}


class TestNormalizePkg:
    """Test suite for the normalize_pkg helper."""

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("pyjwt", "pyjwt"),
            ("PyJWT", "pyjwt"),
            ("scikit-learn", "scikit_learn"),
            ("scikit_learn", "scikit_learn"),
            ("SciKit-Learn", "scikit_learn"),
            ("Pillow", "pillow"),
            ("SciKit-Learn>=10.0", "scikit_learn"),
        ],
    )
    def test__canonical(self, name: str, expected: str) -> None:
        """_canonical lowercases and replaces hyphens with underscores."""
        assert _canonical(name) == expected


class TestMkSrcFormatter:
    """Test suite for the mk_src_formatter function."""

    @pytest.fixture
    def stmt(self) -> ast.stmt:
        """AST import statement fixture."""
        return ast.parse("import foo.bar").body[0]

    @pytest.mark.parametrize("verbose", [True, False])
    def test_no_show_all_on_status_ok(self, stmt: ast.stmt, verbose: bool) -> None:
        """If the import is expected, we do not show it."""
        cfg = AppConfig(
            file_names=[Path()],
            known_extra=[Package("foo")],
            known_missing=[],
            provides=Packages([]),
            verbose=verbose,
            show_all=False,
        )
        fn = cfg.mk_src_formatter()
        assert not list(fn("src.py", Dependency.OK, Module("foo"), stmt))

    @pytest.mark.parametrize(
        "verbose, show_all, cause, expected",
        [
            (True, False, "!", "!NA src.py:1 foo"),
            (True, True, "!", "!NA src.py:1 foo"),
            (True, True, " ", " OK src.py:1 foo"),
            (False, False, "!", "! foo"),
            (False, True, "!", "! foo"),
            (False, True, " ", "  foo"),
        ],
    )
    def test(  # pylint: disable=too-many-arguments
        self,
        stmt: ast.stmt,
        verbose: bool,
        show_all: bool,
        cause: str,
        expected: str,
    ) -> None:
        """MkSrcFormatter generic tests."""
        cfg = AppConfig(
            file_names=[Path()],
            known_extra=[],
            known_missing=[],
            provides=Packages([]),
            verbose=verbose,
            show_all=show_all,
        )
        fn = cfg.mk_src_formatter()
        assert next(fn("src.py", Dependency(cause), Module("foo"), stmt)) == expected

    def test_cache(self, stmt: ast.stmt) -> None:
        """Test the cache mechanism for the formatter."""
        cfg = AppConfig(file_names=[Path()])
        fn = cfg.mk_src_formatter()
        assert list(fn("src.py", Dependency.NA, Module("foo"), stmt))
        assert not list(fn("src.py", Dependency.NA, Module("foo"), stmt))
