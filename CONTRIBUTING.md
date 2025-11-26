# Contributing to SIEV: Structured dIalectical rEasoning eValuation

Thank you for your interest in contributing to SIEV! This document provides guidelines for contributing to the project.

## 📋 Contributor License Agreement (CLA)

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit [https://cla.opensource.microsoft.com](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

## 🚀 Quick Start for Contributors

### Prerequisites

- Python 3.8+
- Git
- Virtual environment support

### Setup Development Environment

1. **Fork and Clone**

   ```bash
   git clone https://github.com/yourusername/siev.git
   cd siev
   ```

2. **Setup Environment**

   ```bash
   chmod +x setup.sh
   ./setup.sh
   source ../SIEVenv/bin/activate
   ```

3. **Validate Setup**

   ```bash
   ./validate.sh
   ```

## 🔧 Development Guidelines

### Code Style

- Follow PEP 8 for Python code
- Use descriptive variable and function names
- Add docstrings for all classes and functions
- Keep functions focused and small

### Testing

- Test all changes with `./validate.sh`
- Ensure shell scripts pass syntax validation
- Test both GSM and MMLU evaluation paths

### Documentation

- Update relevant documentation for any changes
- Keep README.md current with new features
- Update API documentation if interfaces change

## 📝 Types of Contributions

### 🐛 Bug Reports

- Use GitHub Issues
- Include system information (OS, Python version)
- Provide steps to reproduce
- Include error messages and logs

### ✨ Feature Requests

- Use GitHub Issues with feature request template
- Describe the use case
- Explain expected behavior
- Consider backwards compatibility

### 🔨 Pull Requests

1. **Before Submitting**
   - Run `./validate.sh` to ensure everything works
   - Test with both evaluation scripts
   - Update documentation as needed
   - Add or update tests if applicable

2. **Pull Request Process**
   - Create descriptive title and description
   - Reference any related issues
   - Keep changes focused and atomic
   - Be responsive to review feedback

### 📚 Documentation Improvements

- Fix typos and improve clarity
- Add examples and use cases
- Improve API documentation
- Update troubleshooting guides

## 🏗️ Project Structure

```
siev/
├── src/                     # Core framework code
├── docs/                    # Documentation
├── .env.example             # Environment configuration template
├── scripts/                 # Evaluation and analysis scripts
├── prompts/                 # Dialectical prompts
├── evaluate-gsm.sh         # GSM evaluation entry point
├── evaluate-mmlu.sh        # MMLU evaluation entry point
└── validate.sh             # Setup validation
```

## 🎯 Areas for Contribution

### High Priority

- Additional model support (new APIs, local models)
- Performance optimizations
- Enhanced error handling
- More comprehensive testing

### Medium Priority

- Additional benchmark support
- Visualization improvements
- Documentation enhancements
- Example use cases

### Research Areas

- New dialectical reasoning techniques
- Alternative evaluation methodologies
- Prompt engineering improvements
- Results analysis frameworks

## 🤝 Community Guidelines

### Be Respectful

- Use inclusive language
- Respect different perspectives and experiences
- Provide constructive feedback
- Help others learn and grow

### Be Collaborative

- Share knowledge and best practices
- Ask questions when unclear
- Offer help to other contributors
- Build on each other's work

## 📞 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **Documentation**: Check docs/ directory first
- **Validation**: Use `./validate.sh` for setup issues
- **Examples**: See docs/API_SETUP.md for usage examples

## 🏷️ Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes

## 📄 License

By contributing to SIEV, you agree that your contributions will be licensed under the MIT License.

## 🤝 Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

---

**Thank you for making SIEV better! 🎉**
