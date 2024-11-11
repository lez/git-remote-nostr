from setuptools import setup, find_packages
from codecs import open # For a consistent encoding
from os import path
import re


here = path.dirname(__file__)


with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


def read(*names, **kwargs):
    with open(
        path.join(here, *names),
        encoding=kwargs.get("encoding", "utf8")
    ) as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name='git-remote-nostr',

    version=find_version('git_remote_nostr', '__init__.py'),

    description='A transparent bidirectional bridge between Git and Nostr',
    long_description=long_description,

    url='https://githab.com/lez/git-remote-nostr',

    author='Lez',
    author_email='lez@nostr.hu',

    license='MIT',

    classifiers=[
        'Development Status :: 1 - Proof of Concept',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Version Control',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],

    keywords='git remote nostr blossom',

    packages=find_packages(),

    install_requires=[
        'monstr==0.1.9',
        'aiohttp>=3.9.5,<4'
    ],

    entry_points={
        'console_scripts': [
            'git-remote-nostr+blossom=git_remote_nostr.cli.helper:main',
#            'git-nostr-manage=git_remote_nostr.cli.manage:main',
        ],
    },
)
