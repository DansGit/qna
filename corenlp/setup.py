import os
from distutils.core import setup

PACKAGE = "corenlp"
NAME = "corenlp-python"
DESCRIPTION = "A Stanford Core NLP wrapper"
AUTHOR = "Hiroyoshi Komatsu"
AUTHOR_EMAIL = "hiroyoshi.komat@gmail.com"
URL = "https://bitbucket.org/torotoki/corenlp-python"
VERSION = "3.3.0-0"

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=read("README.md"),
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    include_package_data=True,
    packages=['corenlp'],
    package_dir = {'corenlp': 'corenlp'},
    package_data = {
        "corenlp": ["default.properties"]
    },
    install_requires=[
        "pexpect >= 2.4",
        "unidecode >= 0.04.12",
        "xmltodict >= 0.4.6",
    ],
    # data_files = [
    #     ('corenlp', ["default.properties"]),
    # ],
    # package_data=find_package_data(
    #     PACKAGE,
    #     only_in_packages=False
    # )
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Programming Language :: Python",
    ],
)
