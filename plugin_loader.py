import os
import sys
import traceback
import importlib.util


def load_plugins(registry, plugins_dir: str, logger=None):
    """
    Loads plugins from plugins_dir.

    Plugin file requirements:
      - Python file: *.py
      - Exposes function: register(registry)
    """
    plugins_dir = os.path.abspath(plugins_dir)

    if not os.path.isdir(plugins_dir):
        if logger:
            logger.log(f"Plugins: directory not found: {plugins_dir}")
        return

    for filename in sorted(os.listdir(plugins_dir)):
        if not filename.lower().endswith(".py"):
            continue
        if filename.startswith("_"):
            continue

        path = os.path.join(plugins_dir, filename)
        mod_name = f"cmr_plugin_{os.path.splitext(filename)[0]}"

        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                raise RuntimeError("Failed to build spec/loader")

            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            if not hasattr(module, "register"):
                if logger:
                    logger.log(f"Plugins: {filename} missing register(registry)")
                continue

            module.register(registry)

            if logger:
                logger.log(f"Plugins: loaded {filename}")

        except Exception as e:
            if logger:
                logger.log(f"Plugins: ERROR loading {filename}: {type(e).__name__}: {e}")
                tb = traceback.format_exc()
                for line in tb.splitlines():
                    logger.log(line)
