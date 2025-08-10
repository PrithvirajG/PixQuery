# Documentation Maintenance Guide

## Documentation Philosophy

This documentation follows a **branch-structured** approach designed to optimize Claude Code's ability to understand and assist with the project. Each file serves a specific purpose and maintains under 300 lines for effective chunking and retrieval.

## File Structure and Purposes

### Core Documentation Files
- **overview.md**: High-level architecture, tech stack, and component relationships
- **setup.md**: Installation steps, dependencies, environment configuration
- **running.md**: Operational guides for different deployment scenarios
- **testing.md**: Testing strategy, coverage requirements, and debugging
- **guidelines.md**: Code style, workflow processes, and best practices
- **troubleshooting.md**: Common issues, error patterns, and solutions
- **future.md**: Limitations, scalability concerns, and improvement roadmap
- **thinking_cases.md**: Problem-solving approaches and decision-making examples
- **update_docs.md**: This file - how to maintain and extend documentation

### Specialized Documentation (if needed)
- **api.md**: Detailed API reference with all endpoints and examples
- **models.md**: AI model specifications, training details, and performance metrics
- **deployment.md**: Production deployment guides and infrastructure requirements

## Documentation Standards

### Formatting Rules

#### Headers and Structure
```markdown
# Main Title (H1) - One per file
## Major Section (H2) - Main content organization  
### Subsection (H3) - Detailed breakdowns
#### Minor Section (H4) - Specific details only when needed
```

#### Code Blocks
- Use language-specific syntax highlighting: ```python, ```bash, ```sql
- Include brief explanations before complex code blocks
- Show both commands and expected outputs where helpful

#### Lists and Organization
- Use bullet points for features, requirements, and steps
- Use numbered lists for sequential procedures only
- Keep list items concise (1-2 lines maximum)

#### Cross-References
```markdown
# Good: Relative links with descriptive text
See [setup instructions](./setup.md) for installation details.
Refer to the [testing guide](./testing.md#unit-tests) for unit test examples.

# Bad: Absolute paths or unclear references  
See /docs/setup.md
Check the other file for details
```

### Content Guidelines

#### File Length Limits
- **Target**: 150-250 lines per file
- **Maximum**: 300 lines before considering file split
- **Minimum**: 50 lines (combine smaller files)

#### Writing Style
- **Clear and concise**: Avoid unnecessary technical jargon
- **Action-oriented**: Start sections with verbs (Configure, Install, Test)
- **Specific examples**: Include actual commands and expected outputs
- **Assume basic knowledge**: Don't explain fundamental Git/Python concepts

#### Code Examples
- **Runnable commands**: All bash commands should work as-is
- **Real file paths**: Use actual project file paths, not placeholders
- **Expected outputs**: Show what successful commands produce
- **Error cases**: Include common failure scenarios and solutions

## When to Update Documentation

### Immediate Updates Required
- **New API endpoints**: Update both overview.md and create API examples
- **Dependency changes**: Update setup.md with new requirements
- **Configuration changes**: Update environment variables and config files
- **New test files**: Update testing.md with coverage information

### Weekly/Release Updates
- **Performance metrics**: Update any benchmark numbers or resource requirements
- **Known issues**: Add new troubleshooting entries from support requests
- **Process improvements**: Update guidelines.md with refined workflows

### Major Version Updates
- **Architecture changes**: Completely review overview.md and component relationships
- **Technology stack updates**: Review all dependencies and update installation guides
- **Breaking changes**: Update future.md with migration considerations

## How to Update Specific Files

### overview.md Updates
**When**: Architecture changes, new components, technology updates
```bash
# Check for new source files that need documentation
find src/ -name "*.py" -newer docs/overview.md

# Review git log for structural changes
git log --since="1 month ago" --oneline src/
```

**Common Updates**:
- Add new modules to component list
- Update technology versions in tech stack
- Revise data flow diagrams for new processing steps
- Update integration points for new external services

### setup.md Updates  
**When**: Dependency changes, installation process updates
```bash
# Check for requirement file changes
git log --since="1 week ago" requirements*.txt

# Verify installation steps still work
cd /tmp && git clone <repo> && cd PixQuery/backend && ./setup_test.sh
```

**Common Updates**:
- New Python dependencies or version requirements
- Additional system dependencies (GPU drivers, system packages)  
- Changed environment variables or configuration files
- Updated Docker service versions

### running.md Updates
**When**: New startup procedures, deployment methods, operational changes
```bash
# Test all documented commands still work
bash -n docs/running.md  # Extract and validate shell commands
```

**Common Updates**:
- New command-line options for services
- Changed default ports or connection strings
- Additional monitoring or debugging commands
- New deployment scenarios (Docker, Kubernetes, etc.)

### testing.md Updates
**When**: New test files, coverage changes, testing infrastructure updates
```bash
# Find new test files
find tests/ -name "*.py" -newer docs/testing.md

# Check current test coverage
pytest --cov=src --cov-report=term-missing | grep TOTAL
```

**Common Updates**:
- Document new test files and their purpose
- Update coverage requirements and current metrics
- Add new testing procedures or debugging steps
- Update CI/CD pipeline documentation

## Approval Process

### Self-Review Checklist
Before committing documentation changes:

- [ ] All links work correctly (use relative paths)
- [ ] Code examples are tested and work as shown
- [ ] File stays under 300 lines
- [ ] New content follows formatting standards
- [ ] Cross-references updated in related files
- [ ] Spelling and grammar checked

### Peer Review Requirements
For major documentation changes:
- **Architecture updates**: Require review from system architect
- **Setup/deployment changes**: Test on clean environment
- **API documentation**: Validate against actual API behavior
- **Troubleshooting additions**: Confirm solutions work

### Documentation Testing
```bash
# Validate markdown formatting
markdownlint docs/*.md

# Test code blocks extraction and execution
grep -A 10 "```bash" docs/*.md | bash -n

# Check for broken links
find docs/ -name "*.md" -exec grep -l "](\./" {} \; | xargs linkcheck

# Verify file sizes
wc -l docs/*.md | grep -E '[3-9][0-9]{2,}'  # Find files >300 lines
```

## File Organization Principles

### When to Create New Files
Create a new documentation file when:
- Existing file exceeds 300 lines
- Content covers a distinct functional area
- Information is referenced from multiple other files
- Content requires different update frequencies

### When to Split Files
Split an existing file when:
```bash
# Check file length
wc -l docs/overview.md
# If >300 lines, consider splitting

# Common split patterns:
# overview.md → overview.md + architecture.md + components.md
# setup.md → setup.md + dependencies.md + configuration.md
# testing.md → testing.md + test_data.md + ci_cd.md
```

### File Naming Conventions
- Use descriptive, hyphenated names: `test-data-management.md`
- Avoid abbreviations: `troubleshooting.md` not `trouble.md`  
- Use consistent prefixes for related files: `api-endpoints.md`, `api-examples.md`

## Documentation Automation

### Automated Updates (Recommended)
```bash
# Create update script: scripts/update_docs.sh
#!/bin/bash

# Update API endpoint documentation
python scripts/extract_api_endpoints.py > docs/api_reference.md

# Update test coverage numbers  
pytest --cov=src --cov-report=json
python scripts/update_coverage_docs.py docs/testing.md

# Update dependency list
pip freeze | python scripts/update_requirements_docs.py docs/setup.md

echo "Documentation updated successfully"
```

### Git Hooks Integration
```bash
# .git/hooks/pre-commit
#!/bin/bash

# Check for outdated documentation
if git diff --cached --name-only | grep -E "\.(py|txt)$"; then
    echo "Code changes detected. Consider updating documentation."
    echo "Run: make update-docs"
fi

# Validate markdown
markdownlint docs/*.md || exit 1
```

## Measuring Documentation Quality

### Metrics to Track
- **File count and average length**: Keep files focused and readable
- **Cross-reference density**: More links = better navigation
- **Code example coverage**: Percentage of commands that are tested
- **Update frequency**: Documentation should change with code

### Quality Checks
```bash
# Count cross-references per file
grep -c "\.md)" docs/*.md

# Find files without code examples
grep -L "```" docs/*.md

# Identify stale documentation (older than code)
for doc in docs/*.md; do
    if [ "$doc" -ot src/ ]; then
        echo "Stale: $doc"
    fi
done
```

### User Feedback Integration
- Monitor setup success rates from new contributors
- Track common support questions that indicate missing documentation
- Review onboarding feedback for documentation gaps

## Migration and Versioning

### Versioning Documentation
- Tag documentation versions with code releases
- Maintain compatibility notes for major version changes
- Archive outdated documentation rather than deleting

### Legacy Documentation Migration
When migrating from existing documentation:
1. **Audit existing content**: What's still relevant?
2. **Map to new structure**: Where does each section belong?
3. **Update examples**: Ensure all commands and paths are current
4. **Test thoroughly**: Verify all procedures work end-to-end