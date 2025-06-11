# Jira Fork Tool

A comprehensive tool for creating and maintaining synchronized copies of Jira projects across different organizations while preserving complete data fidelity and maintaining ticket number synchronization.

## Overview

The Jira Fork Tool addresses the complex challenge of maintaining ticket number synchronization while ensuring complete data fidelity across all Jira entities including issues, comments, attachments, and metadata. The tool leverages a multi-layered approach combining sequential issue processing, gap detection algorithms, and robust error handling to overcome Jira's inherent limitations around issue number control.

## Key Features

- **Ticket Number Synchronization**: Maintains perfect numerical alignment between source and destination issues
- **Complete Data Fidelity**: Transfers all issue content, attachments, comments, and metadata
- **Gap Detection and Handling**: Automatically handles missing issue numbers in source projects
- **Incremental Synchronization**: Supports ongoing synchronization after initial fork
- **Robust Error Handling**: Comprehensive error recovery and retry mechanisms
- **Rate Limit Management**: Intelligent handling of Jira API rate limits
- **Multi-Authentication Support**: API tokens, OAuth 2.0, and JWT authentication
- **Web Dashboard**: Real-time progress monitoring and configuration management
- **Enterprise Security**: Secure credential management and audit logging

## Architecture

The tool is architected as a modular Python application with distinct components:

- **Authentication Manager**: Handles all authentication methods and credential management
- **Project Analyzer**: Analyzes source projects and plans synchronization strategy
- **Issue Synchronizer**: Core engine for sequential issue processing and synchronization
- **Attachment Handler**: Manages file download, storage, and upload operations
- **Comment Processor**: Handles comment synchronization with formatting preservation
- **State Manager**: Provides persistent state management and recovery capabilities

## Installation

### Prerequisites

- Python 3.8 or later
- 4GB RAM minimum (16GB recommended for large projects)
- High-speed internet connection
- Access to both source and destination Jira instances

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/jira-fork-tool.git
cd jira-fork-tool

# Install dependencies
pip install -r requirements.txt

# Configure the tool
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your Jira instance details

# Run the tool
python -m jira_fork_tool --config config/config.yaml
```

## Configuration

The tool uses YAML configuration files for setup. See `config/config.example.yaml` for a complete configuration template.

### Basic Configuration

```yaml
source:
  url: "https://source.atlassian.net"
  auth:
    type: "api_token"
    email: "user@example.com"
    token: "your-api-token"
  project_key: "SOURCE"

destination:
  url: "https://destination.atlassian.net"
  auth:
    type: "api_token"
    email: "user@example.com"
    token: "your-api-token"
  project_key: "DEST"

sync:
  preserve_numbers: true
  handle_gaps: true
  include_attachments: true
  include_comments: true
```

## Usage

### Basic Project Fork

```bash
# Fork a complete project
python -m jira_fork_tool fork --source-project SOURCE --dest-project DEST

# Fork with custom configuration
python -m jira_fork_tool fork --config custom-config.yaml

# Resume interrupted synchronization
python -m jira_fork_tool resume --sync-id abc123
```

### Incremental Synchronization

```bash
# Sync changes since last update
python -m jira_fork_tool sync --incremental

# Sync specific date range
python -m jira_fork_tool sync --since "2025-01-01" --until "2025-01-31"
```

### Web Dashboard

```bash
# Start the web dashboard
python -m jira_fork_tool dashboard --port 8080

# Access at http://localhost:8080
```

## Documentation

- [Installation Guide](docs/installation.md)
- [Configuration Reference](docs/configuration.md)
- [User Guide](docs/user-guide.md)
- [API Documentation](docs/api.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development Guide](docs/development.md)

## Project Structure

```
jira-fork-tool/
├── src/jira_fork_tool/          # Main application code
│   ├── auth/                    # Authentication components
│   ├── sync/                    # Synchronization engine
│   ├── api/                     # Jira API integration
│   ├── config/                  # Configuration management
│   ├── ui/                      # Web dashboard
│   └── utils/                   # Utility functions
├── tests/                       # Test suite
├── docs/                        # Documentation
├── scripts/                     # Utility scripts
├── examples/                    # Example configurations
└── config/                      # Configuration templates
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone and setup development environment
git clone https://github.com/yourusername/jira-fork-tool.git
cd jira-fork-tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linting
flake8 src/ tests/
black src/ tests/
```

## Testing

The project includes comprehensive testing:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=jira_fork_tool

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/
```

## Security

Security is a top priority. The tool implements:

- Secure credential storage and transmission
- Encryption of sensitive data
- Comprehensive audit logging
- Access control integration
- Regular security assessments

Please report security vulnerabilities privately to security@example.com.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/jira-fork-tool/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/jira-fork-tool/discussions)
- **Email**: support@example.com

## Roadmap

- [ ] Support for Jira Server/Data Center
- [ ] Advanced field mapping capabilities
- [ ] Bulk project migration
- [ ] Integration with CI/CD pipelines
- [ ] Advanced analytics and reporting
- [ ] Plugin architecture for custom processors

## Acknowledgments

- Atlassian for the comprehensive Jira REST API
- The Python community for excellent libraries
- Contributors and testers who help improve the tool

---

**Note**: This tool is not officially affiliated with Atlassian. Jira is a trademark of Atlassian.

