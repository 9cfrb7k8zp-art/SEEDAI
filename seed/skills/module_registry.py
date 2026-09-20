# ==========================================================
# FILE: module_registry.py
# PATH: C:\\SEED_ROOT\\seed\\skills\\module_registry.py
# VERSION: 7.0.0-FACADE
# BUILD: LEGACY-COMPATIBILITY / CORE-AUTHORITY
#
# The former skills registry is preserved as
# module_registry_legacy_blueprint.py.
# This path now delegates to seed.core.module_registry.
# ==========================================================

from seed.core.module_registry import ModuleRegistry as _CoreModuleRegistry


_core_registry = _CoreModuleRegistry()


class ModuleRegistry:
    """Legacy API facade over the authoritative core registry."""

    @classmethod
    def register(cls, module_id=None, name=None, parent_id=None):
        key = name or module_id or "UNKNOWN_MODULE"
        result = _core_registry.register(
            key,
            inventory={
                "legacy_module_id": module_id,
                "legacy_parent_id": parent_id,
                "legacy_api": True,
            },
        )
        return result

    @classmethod
    def list_all(cls):
        return [item.get("name") for item in _core_registry.all()]

    @classmethod
    def get_metadata(cls, module_id):
        return _core_registry.get(module_id)

    @classmethod
    def exists(cls, module_id):
        return _core_registry.get(module_id) is not None


def handle_skill_done(module_id=None, note=None, parent_id=None):
    if module_id is None:
        return None
    if ModuleRegistry.exists(module_id):
        return module_id
    ModuleRegistry.register(module_id, name="UNKNOWN_MODULE", parent_id=parent_id)
    return module_id


def register_modules_bulk(modules):
    for module in modules or []:
        ModuleRegistry.register(
            module_id=module.get("module_id"),
            name=module.get("name"),
            parent_id=module.get("parent_id"),
        )


__all__ = [
    "ModuleRegistry",
    "handle_skill_done",
    "register_modules_bulk",
]
