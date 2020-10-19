#!/usr/bin/env python3

import setuptools

import funcpipes
long_description = funcpipes.__doc__

setuptools.setup(
    name='funcpipes',
    version='0.0.1',
    author='Mihail Georgiev',
    author_email='misho88@gmail.com',
    description='Pipes - Functions for Building Data Pipelines',
    long_description=long_description,
    long_description_content_type='text/plain',
    url='https://github.com/misho88/pipes',
    packages=setuptools.find_packages(),
    python_requires='>=3.6',
    py_modules=['funcpipes']
)
