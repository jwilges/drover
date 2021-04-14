import nox

nox.options.sessions = ['dev-3.9']
nox.options.error_on_missing_interpreters = True


@nox.session(python=['3.6', '3.7', '3.8', '3.9'])
def dev(session):
    session.install('-r', 'requirements.build.txt')
    session.install('-r', 'requirements.dev.txt')
    session.install('-c', 'requirements.txt', '-e', '.')
    if not session.posargs:
        return
    session.run('invoke', *session.posargs)
