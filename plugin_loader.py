import importlib.util
import os
import sys
import traceback


def _add_sys_path(path: str):
    """Add path to sys.path once, keeping plugin dependency precedence."""
    normalized = os.path.normcase(os.path.normpath(path))
    for existing in sys.path:
        if os.path.normcase(os.path.normpath(existing)) == normalized:
            return
    sys.path.insert(0, path)


def _plugin_dependency_dirs(plugins_dir: str, plugin_path: str):
    """Return candidate dependency dirs for a plugin/module path."""
    candidates = [
        os.path.join(plugins_dir, "_shared_deps"),
    ]

    if os.path.isdir(plugin_path):
        candidates.extend(
            [
                plugin_path,
                os.path.join(plugin_path, "deps"),
                os.path.join(plugin_path, "libs"),
                os.path.join(plugin_path, "vendor"),
                os.path.join(plugin_path, "site-packages"),
            ]
        )
    else:
        stem, _ = os.path.splitext(os.path.basename(plugin_path))
        plugin_dir = os.path.join(plugins_dir, stem)
        candidates.extend(
            [
                plugin_dir,
                os.path.join(plugins_dir, f"{stem}_deps"),
                os.path.join(plugins_dir, f"{stem}_libs"),
                os.path.join(plugin_dir, "deps"),
                os.path.join(plugin_dir, "libs"),
                os.path.join(plugin_dir, "vendor"),
                os.path.join(plugin_dir, "site-packages"),
            ]
        )

    return [d for d in candidates if os.path.isdir(d)]


def _iter_plugin_entries(plugins_dir: str):
    """Yield plugin entries as (display_name, module_name, load_path)."""
    for filename in sorted(os.listdir(plugins_dir)):
        if filename.startswith("_"):
            continue

        path = os.path.join(plugins_dir, filename)

        if os.path.isfile(path) and filename.lower().endswith(".py"):
            mod_stem = os.path.splitext(filename)[0]
            yield filename, f"cmr_plugin_{mod_stem}", path
            continue

        if os.path.isdir(path):
            init_py = os.path.join(path, "__init__.py")
            if os.path.isfile(init_py):
                mod_stem = filename
                yield filename, f"cmr_plugin_pkg_{mod_stem}", init_py


def load_plugins(registry, plugins_dir: str, logger=None):
    """
    Loads plugins from plugins_dir.

    Supported plugin formats:
      - Single-file module: plugins/<name>.py
      - Package plugin:      plugins/<name>/__init__.py

    Dependency folders (optional):
      - plugins/_shared_deps/
      - plugins/<name>_deps/ or plugins/<name>_libs/
      - plugins/<name>/deps|libs|vendor|site-packages/

    Plugin requirement:
      - Exposes function: register(registry)
    """
    plugins_dir = os.path.abspath(plugins_dir)

    if not os.path.isdir(plugins_dir):
        if logger:
            logger.log(f"Plugins: directory not found: {plugins_dir}")
        return

    # Allow plugins to import sibling modules or shared dependencies.
    _add_sys_path(plugins_dir)

    if logger:
        logger.log(f"Plugins: scanning directory: {plugins_dir}")

    loaded_count = 0
    failed_count = 0

    for display_name, mod_name, load_path in _iter_plugin_entries(plugins_dir):
        if logger:
            logger.log(f"Plugins: loading {display_name}")

        for dep_dir in _plugin_dependency_dirs(plugins_dir, load_path):
            _add_sys_path(dep_dir)
            if logger:
                logger.log(f"Plugins: dependency path added: {dep_dir}")

        try:
            spec = importlib.util.spec_from_file_location(mod_name, load_path)
            if spec is None or spec.loader is None:
                raise RuntimeError("Failed to build spec/loader")

            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            if not hasattr(module, "register"):
                if logger:
                    logger.log(f"Plugins: {display_name} missing register(registry)")
                continue

            module.register(registry)
            loaded_count += 1

            if logger:
                logger.log(f"Plugins: loaded {display_name}")

        except ModuleNotFoundError as e:
            failed_count += 1
            if logger:
                missing_dep = getattr(e, "name", None) or str(e)
                logger.log(
                    f"Plugins: dependency error in {display_name}: missing module '{missing_dep}'"
                )
                logger.log(
                    "Plugins: add dependency files beside the plugin (deps/libs/vendor/site-packages), then restart MacroCommander"
                )
                tb = traceback.format_exc()
                for line in tb.splitlines():
                    logger.log(line)

        except Exception as e:
            failed_count += 1
            if logger:
                logger.log(f"Plugins: ERROR loading {display_name}: {type(e).__name__}: {e}")
                tb = traceback.format_exc()
                for line in tb.splitlines():
                    logger.log(line)

    if logger:
        logger.log(
            f"Plugins: scan complete (loaded={loaded_count}, failed={failed_count})"
        )
