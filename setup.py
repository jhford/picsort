#!/usr/bin/env python

from setuptools import setup

setup(name='picsort',
      version='1.0',
      description='Safely de-duplicate and sort files',
      author='John H. Ford',
      author_email='john+picsort.johnford@org',
      packages=['picsort'],
      entry_points={
        'console_scripts': [
            'picsort = picsort.sort:main'
        ]
      },
      install_requires=['exifread'],
      url='https://github.com/jhford/picsort',
      license='GPLv2',
      keywords='photography raw nef cr2',
)

