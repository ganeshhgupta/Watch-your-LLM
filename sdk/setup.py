from setuptools import setup, find_packages

setup(
    name="llmobs",
    version="0.1.0",
    description="Lightweight LLM tracing SDK",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "pydantic>=2.0",
    ],
    extras_require={
        "dev": ["pytest", "httpx"],
    },
)
