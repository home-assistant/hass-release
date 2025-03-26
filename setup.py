from setuptools import setup

setup(
    name="hassrelease",
    version="1.0",
    packages=["hassrelease"],
    install_requires=["github3.py>=4.0.1", "click", "pystache", "requests", "toml", "packaging"],
    entry_points={"console_scripts": ["hassrelease = hassrelease.__main__:main"]},
)
