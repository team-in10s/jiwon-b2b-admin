from setuptools import setup, find_packages

setup(
    name="jiwon-b2b-admin",
    packages=find_packages(include=['src', 'src.*']),
    package_dir={'': '.'}
) 