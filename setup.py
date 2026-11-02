from setuptools import setup

setup(
    name="hassrelease",
    version="1.0",
    packages=["hassrelease"],
    python_requires=">=3.14",
    install_requires=["github3.py==3.2.0", "click", "pystache", "requests", "toml", "packaging"],
    entry_points={"console_scripts": ["hassrelease = hassrelease.__main__:main"]},
)
