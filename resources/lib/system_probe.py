import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from resources.lib import dependencies
dependencies._refresh_python_module_paths(list(dependencies.REQUIRED_EXTERNAL_ADDONS))
from resources.lib.system_check import run_probe
run_probe()
