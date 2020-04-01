import shutil
from pathlib import Path

import nox

nox.options.sessions = ['dev-3.8']
nox.options.error_on_missing_interpreters = True


@nox.session(python=['3.7', '3.8'])
def dev(session):
    session.install('-r', 'requirements.dev.txt')
    session.install('-e', '.')
    if not session.posargs:
        return
    mode = session.posargs[0]
    if mode == 'test':
        session.run('pytest')
    elif mode == 'lint':
        session.run('pylint', '--disable', 'C,R', 'drover')
    elif mode == 'coverage':
        session.run('coverage', 'run', '-m', 'pytest', *session.posargs[1:])
        session.run('coverage', 'report')
    elif mode == 'coverage-xml':
        session.run('coverage', 'run', '-m', 'pytest', *session.posargs[1:])
        session.run('coverage', 'xml')
    elif mode == 'wheel':
        release_paths = [Path(path) for path in ('build', 'dist')]
        for path in release_paths:
            if path.exists():
                shutil.rmtree(path)
        session.run('python', 'setup.py', 'sdist', 'bdist_wheel')
