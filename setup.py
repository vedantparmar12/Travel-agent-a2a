from setuptools import setup, find_packages

setup(
    name="travel-agent-system",
    version="1.0.0",
    description="Multi-agent travel planning system using LangGraph",
    author="Travel Agent System",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "langgraph>=0.2.0",
        "langchain>=0.1.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "aiohttp>=3.9.0",
    ],
)