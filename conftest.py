# Root conftest to load lightweight test shims early (load by path to avoid import errors)
import importlib.util
import pathlib

shim_path = pathlib.Path(__file__).parent / 'tests' / '_shims.py'
if shim_path.exists():
	spec = importlib.util.spec_from_file_location('tests._shims', str(shim_path))
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)

	# Remove stray modules that can conflict with tests having same base name in other folders
	import sys
	root = str(pathlib.Path(__file__).parent.resolve())
	for name, m in list(sys.modules.items()):
		if hasattr(m, '__file__'):
			f = getattr(m, '__file__') or ''
			if f:
				fp = str(pathlib.Path(f).resolve())
				# remove modules that originate from ict_trading_system/src to prevent import-file mismatch
				if 'ict_trading_system/src' in fp or fp.startswith(root + '/ict_trading_system/src'):
					del sys.modules[name]

# Additionally, if a module named test_reasoner_factory was imported from another folder, remove it to allow our local test to be discovered
if 'test_reasoner_factory' in sys.modules:
	m = sys.modules['test_reasoner_factory']
	if hasattr(m, '__file__') and m.__file__ and 'ict_trading_system/src' in str(m.__file__):
		del sys.modules['test_reasoner_factory']

# Also ensure any module imported from ict_trading_system/src named like a test is removed
for name, m in list(sys.modules.items()):
	if name.startswith('test_') and hasattr(m, '__file__'):
		try:
			fp = str(pathlib.Path(getattr(m, '__file__')).resolve())
			if 'ict_trading_system/src' in fp:
				del sys.modules[name]
		except Exception:
			continue
