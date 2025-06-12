from setuptools import setup, find_packages

setup(
    name="jira-fork-tool",
    version="1.0.0",
    description="Comprehensive Jira project forking and synchronization tool",
    author="Manus AI",
    author_email="manus@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "requests>=2.31.0",
        "PyYAML>=6.0",
        "click>=8.1.0",
        "Flask>=2.3.0",
        "Jinja2>=3.1.0",
    ],
    entry_points={
        "console_scripts": [
            "jira-fork-tool=jira_fork_tool.main:main",
        ],
    },
    python_requires=">=3.8",
)
