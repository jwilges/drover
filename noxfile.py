import nox


@nox.session(python=['3.8'])
def build(session):
    session.install('-r', 'requirements.dev.txt')
    session.install('-e', '.')
    if not session.posargs:
        return
    if session.posargs[0] == 'test':
        session.run('pytest', 'tests')
    elif session.posargs[0] == 'lint':
        session.run('pylint', '--disable', 'C', 'drover')
