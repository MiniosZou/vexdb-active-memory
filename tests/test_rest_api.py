import importlib


def test_rest_api_module_import_is_lazy_without_creating_app():
    module = importlib.import_module("vexdb_active_memory.rest_api")

    assert hasattr(module, "create_app")
