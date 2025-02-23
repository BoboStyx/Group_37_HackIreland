from setuptools import setup, find_packages

setup(
    name="Agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-dotenv==1.0.0",
        "requests==2.31.0",
        "fastapi==0.109.2",
        "uvicorn==0.27.1",
        "sqlalchemy==2.0.25",
        "pydantic==2.6.1",
        "openai==1.12.0",
        "sentencepiece==0.1.99",
    ],
    python_requires=">=3.8",
) 