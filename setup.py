import ast
import codecs
import os.path
import setuptools


def read(*path_parts, iterate_lines=False):
    source_file_name = os.path.join(*path_parts)
    if not os.path.isfile(source_file_name):
        raise FileNotFoundError(source_file_name)
    with codecs.open(source_file_name, 'r') as source_file:
        return source_file.readlines() if iterate_lines else source_file.read()


def get_version(*path_parts) -> str:
    # See: <https://packaging.python.org/guides/single-sourcing-package-version/>
    for line in read(*path_parts, iterate_lines=True):
        if line.startswith('__version__'):
            return ast.parse(line).body[0].value.s
    raise RuntimeError('Unable to determine version.')


HERE = os.path.abspath(os.path.dirname(__file__))
VERSION = get_version(HERE, 'drover', '__init__.py')
LONG_DESCRIPTION = read(HERE, 'README.md')

setuptools.setup(
    name='drover',
    version=VERSION,
    author='Jeffrey Wilges',
    author_email='jeffrey@wilges.com',
    description='a command-line utility to deploy Python packages to Lambda functions',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    url='https://github.com/jwilges/drover',
    license='BSD',
    packages=setuptools.find_packages(exclude=['tests*']),
    entry_points={
        'console_scripts': ['drover=drover:main'],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python :: 3.8',
        'Environment :: Console',
        'Topic :: Software Development :: Build Tools',
        'Topic :: System :: Distributed Computing',
        'Topic :: System :: Networking',
        'Topic :: System :: Software Distribution',
        'Topic :: Utilities'
    ],
    install_requires=[
        'boto3',
        'pydantic',
        'pyyaml',
        'tqdm',
    ]
)
