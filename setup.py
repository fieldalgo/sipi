"""Include the canonical local workbench in the pure Python wheel."""
from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent
UI_FILES = ('app.js', 'browser-transport.js', 'index.html', 'model.js',
            'saved.css', 'saved.html', 'saved.js', 'styles.css', 'transport.js', 'worker.js')


class BuildPy(build_py):
    def _copies(self):
        target = Path(self.build_lib) / 'sipi' / '_workbench'
        return [(ROOT / 'workbench' / 'desktop' / name, target / name)
                for name in ('engine.py', 'main.py', 'artifacts.py')] + [
            (ROOT / 'workbench' / 'ui' / name, target / 'ui' / name) for name in UI_FILES]

    def run(self):
        super().run()
        for source, target in self._copies():
            self.mkpath(str(target.parent))
            target.write_bytes(source.read_bytes())
        target = Path(self.build_lib) / 'sipi' / '_workbench' / 'ui' / 'notices.txt'
        notice = b'SIPI local Python workbench\n\n'
        for name in ('LICENSE', 'NOTICE', 'workbench/PYTHON_NOTICES.md'):
            notice += ('--- ' + name + ' ---\n').encode('utf-8') + (ROOT / name).read_bytes() + b'\n'
        target.write_bytes(notice)

    def get_outputs(self, include_bytecode=1):
        extra = [str(target) for _, target in self._copies()]
        extra.append(str(Path(self.build_lib) / 'sipi' / '_workbench' / 'ui' / 'notices.txt'))
        return super().get_outputs(include_bytecode) + extra


setup(cmdclass={'build_py': BuildPy})
