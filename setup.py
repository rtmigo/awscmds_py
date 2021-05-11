from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

constants = SourceFileLoader('constants',
                             'awscmds/_constants.py').load_module()

setup(
    name="awscmds",
    version=constants.__dict__['__version__'],
    author="Artёm IG",
    author_email="ortemeo@gmail.com",
    url='https://github.com/rtmigo/awscmds_py#readme',


    #install_requires=['apig_wsgi', 'awslambdaric'],
    packages=['awscmds'],

    description="",

    keywords="amazon aws cli docker".split(),

    long_description=(Path(__file__).parent / 'README.md').read_text(),
    long_description_content_type='text/markdown',

    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: POSIX",
    ],
)
