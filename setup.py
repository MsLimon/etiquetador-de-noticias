import os
from setuptools import setup, find_packages

VERSION = "0.1.a"
THIS_DIR = os.path.dirname(os.path.abspath(__file__))

def license():
    with open(os.path.join(THIS_DIR, "LICENSE"), encoding="utf-8") as f:
        return f.read()

def readme():
    with open(os.path.join(THIS_DIR, "README.md"), encoding="utf-8") as f:
        return f.read()

with open(os.path.join(THIS_DIR, "requirements.txt")) as f:
    requirements = f.read().splitlines()

setup(
    name = 'etiquetador_noticias',
    version = VERSION,
    author = 'Marta Timon',
    author_email = 'ms.timgl@gmail.com',
    description = 'Auditor de transparencia informativa en medios digitales',
    long_description=readme(),
    python_requires=">=3.6.11",
    packages=find_packages(exclude=['tests']),
    license=license(),
    install_requires=requirements,
    # package_data={'': ['data/*']}
)
