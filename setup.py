from setuptools import setup

try:
    import pypandoc
    long_desc = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError):
    long_desc = ''


def get_version():
    with open("saltbot/__init__.py") as f:
        for line in f:
            if line.startswith("__version__"):
                return line[15:-2]
    raise Exception("Could not find version number")

setup(
    name="Saltbot",
    version=get_version(),
    author="Adam Greig",
    author_email="adam@adamgreig.com",
    packages=["saltbot"],
    entry_points={"console_scripts": ["saltbot = saltbot:main"]},
    url="http://github.com/adamgreig/saltbot",
    license="MIT",
    description="IRC bot for Salt deployments",
    long_description=long_desc,
    test_suite="nose.collector",
    tests_require=["nose", "mock"],
    install_requires=[
        "Flask", "irc", "PyYAML"
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Langauge :: Python :: 3.4",
    ],
)
