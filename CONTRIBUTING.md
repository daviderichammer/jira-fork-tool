# Contributing to Jira Fork Tool

We welcome contributions to the Jira Fork Tool! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a new branch for your feature or bug fix
4. Make your changes
5. Test your changes thoroughly
6. Submit a pull request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/jira-fork-tool.git
cd jira-fork-tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt
pip install -e .

# Install pre-commit hooks
pre-commit install
```

## Code Standards

### Python Code Style

- Follow PEP 8 style guidelines
- Use Black for code formatting
- Use isort for import sorting
- Maximum line length: 88 characters
- Use type hints for all functions and methods

### Code Quality

- Write comprehensive docstrings for all modules, classes, and functions
- Include type hints for all function parameters and return values
- Maintain test coverage above 90%
- Follow the existing code structure and patterns

### Testing

- Write unit tests for all new functionality
- Include integration tests for API interactions
- Use pytest for testing framework
- Mock external dependencies in unit tests

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=jira_fork_tool

# Run specific test file
pytest tests/test_auth.py

# Run tests with verbose output
pytest -v
```

### Documentation

- Update README.md for user-facing changes
- Add docstrings to all new functions and classes
- Update configuration examples if needed
- Include examples in docstrings where helpful

## Pull Request Process

1. **Create a feature branch**: `git checkout -b feature/your-feature-name`
2. **Make your changes**: Implement your feature or bug fix
3. **Add tests**: Ensure your changes are covered by tests
4. **Run the test suite**: Make sure all tests pass
5. **Update documentation**: Update relevant documentation
6. **Commit your changes**: Use clear, descriptive commit messages
7. **Push to your fork**: `git push origin feature/your-feature-name`
8. **Create a pull request**: Submit a PR with a clear description

### Pull Request Guidelines

- **Title**: Use a clear, descriptive title
- **Description**: Explain what your changes do and why
- **Testing**: Describe how you tested your changes
- **Breaking changes**: Clearly mark any breaking changes
- **Related issues**: Reference any related GitHub issues

### Commit Message Format

Use the conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(auth): add OAuth 2.0 authentication support
fix(sync): handle rate limiting errors correctly
docs(readme): update installation instructions
```

## Code Review Process

1. All pull requests require review from at least one maintainer
2. Address all review comments before merging
3. Ensure all CI checks pass
4. Squash commits if requested by reviewers

## Issue Reporting

When reporting issues:

1. **Search existing issues** first to avoid duplicates
2. **Use the issue template** if available
3. **Provide detailed information**:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment details (OS, Python version, etc.)
   - Log files or error messages
4. **Label appropriately** (bug, enhancement, question, etc.)

## Feature Requests

For feature requests:

1. **Check existing issues** for similar requests
2. **Describe the use case** clearly
3. **Explain the expected behavior**
4. **Consider implementation complexity**
5. **Be open to discussion** about alternative approaches

## Security Issues

For security-related issues:

1. **Do not create public issues** for security vulnerabilities
2. **Email security@example.com** with details
3. **Include steps to reproduce** if applicable
4. **Allow time for response** before public disclosure

## Development Guidelines

### Architecture Principles

- **Modularity**: Keep components loosely coupled
- **Testability**: Design for easy testing
- **Configuration**: Make behavior configurable
- **Error handling**: Provide clear error messages
- **Logging**: Include comprehensive logging
- **Documentation**: Document all public interfaces

### API Design

- **Consistency**: Follow existing patterns
- **Backward compatibility**: Avoid breaking changes
- **Error handling**: Return meaningful error messages
- **Rate limiting**: Respect API rate limits
- **Authentication**: Handle auth failures gracefully

### Performance Considerations

- **Memory usage**: Optimize for large projects
- **Network efficiency**: Minimize API calls
- **Concurrent processing**: Use parallelization where safe
- **Progress reporting**: Provide user feedback
- **Resumability**: Support interrupted operations

## Release Process

1. **Version bumping**: Follow semantic versioning
2. **Changelog**: Update CHANGELOG.md
3. **Testing**: Run full test suite
4. **Documentation**: Update version-specific docs
5. **Tagging**: Create git tag for release
6. **Distribution**: Build and upload packages

## Community Guidelines

- **Be respectful** and inclusive
- **Help others** learn and contribute
- **Share knowledge** through documentation and examples
- **Provide constructive feedback** in reviews
- **Follow the code of conduct**

## Getting Help

- **Documentation**: Check the docs/ directory
- **Issues**: Search existing GitHub issues
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact maintainers at support@example.com

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes for significant contributions
- GitHub contributor statistics

Thank you for contributing to the Jira Fork Tool!

