from pathlib import Path

from check_dependencies.mapping import (
    DependencyMapping,
    create_mapping,
    gather_venv_mappings,
    get_package_name_from_directory,
    parse_venv_config,
)


def test_parse_example_config() -> None:
    config = parse_venv_config("""
some = data
home = c:\\path\\to\\python
more = data
include-system-site-packages = false
further = data
""")
    assert config.base_installation_path == Path("c:\\path\\to\\python")
    assert not config.include_base_site_packages


def test_create_mapping() -> None:
    mapping = create_mapping(
        "mapped_package",
        """
../../Scripts/some.exe,sha256=vv43hgw89hcoanuv4jkgnnawuiogbek4j,7435
_mapped_import_file.py,sha256=2jinvvJ_mJtFWwq2c5r0kLKA2QhQDJT_lb85CBc0UcU,22589
mapped_import/__init__.py,sha256=98abxVfn8od1jJaTIr65YrYrIb7zMKbOJ5o68ryE2O0,2094
mapped_import\\main.py,sha256=X8eIpGlmHfnp7zazp5mdav228Itcf2lkiMP0tLU6X9c,140
mapped_package-11.1.0.dist-info/LICENSE,sha256=Y6m7FH97jUPSEfBgAP5AYGc5rZP71csfhEvHQPi8Uew,56662
mapped_package-11.1.0.dist-info/METADATA,sha256=sYK2WLlgLj7uN9DKsiS93-M9CuOHSiogmkVnvgc56Aw,9313
mapped_package-11.1.0.dist-info\\WHEEL,sha256=pWXrJbnZSH-J-PhYmKs2XNn4DHCPNBYq965vsBJBFvA,101
mapped_package-11.1.0.dist-info/top_level.txt,sha256=riZqrk-hyZqh5f1Z0Zwii3dKfxEsByhu9cU9IODF-NY,4
mapped_package-11.1.0.dist-info/zip-safe,sha256=frcCV1k9oG9oKj3dpUqdJg1PxRT2RSN_XKdLCPjaYaY,2
mapped_package-11.1.0.dist-info/INSTALLER,sha256=HLHRd3rVxZqLVn0Nby492_jJUNACT5LifwfFYrwaW0E,12
mapped_package-11.1.0.dist-info/RECORD,,
""",
    )
    assert mapping.pip_name == "mapped_package"
    assert mapping.import_names == ("_mapped_import_file", "mapped_import")


def test_package_name_extraction() -> None:
    assert (
        get_package_name_from_directory("mapped_package-11.1.0.dist-info")
        == "mapped_package"
    )


def test_integration() -> None:
    mappings = gather_venv_mappings(
        "my_package_in_development", Path(__file__).parent / "mapping"
    )
    assert mappings == {
        DependencyMapping("some_package", ("some_package",)),
        DependencyMapping("mapped_package", ("_mapped_import_file", "mapped_import")),
    }
