# PixQuery Backend Documentation

## Overview

This documentation provides comprehensive guidance for understanding, developing, and maintaining the PixQuery backend - an AI-powered local photo organizer with semantic search capabilities.

The documentation is structured for both human readability and Claude Code assistance, with each file focused on specific aspects and kept under 300 lines for optimal chunking and retrieval.

## Documentation Structure

### Core Documentation

#### [Overview](./overview.md)
High-level architecture, tech stack, key components, and design patterns. Start here to understand the system structure and data flow.

#### [Setup](./setup.md)
Step-by-step installation guide, dependency management, environment configuration, and verification procedures.

#### [Running](./running.md)
Operational guides for development, staging, and production modes. Includes service management, CLI operations, and monitoring.

#### [Testing](./testing.md)
Testing strategy, current test coverage, how to add new tests, and debugging test failures.

#### [Guidelines](./guidelines.md) 
Code style standards, architecture patterns, Git workflow, and development best practices.

#### [Troubleshooting](./troubleshooting.md)
Common issues, diagnostic procedures, recovery strategies, and prevention techniques.

#### [Future](./future.md)
Current limitations, performance roadmap, security considerations, and long-term architecture evolution.

#### [Thinking Cases](./thinking_cases.md)
Problem-solving approaches, decision frameworks, edge case handling, and debugging methodologies.

#### [Update Docs](./update_docs.md)
How to maintain and extend this documentation, including formatting standards and approval processes.

## Quick Navigation

### Getting Started
1. **New to PixQuery?** → [Overview](./overview.md) → [Setup](./setup.md) → [Running](./running.md)
2. **Setting up development?** → [Setup](./setup.md) → [Guidelines](./guidelines.md) → [Testing](./testing.md)
3. **Encountering issues?** → [Troubleshooting](./troubleshooting.md) → [Thinking Cases](./thinking_cases.md)

### By Role

#### **Developers**
- [Guidelines](./guidelines.md) - Code style and workflow
- [Testing](./testing.md) - Test strategy and debugging
- [Thinking Cases](./thinking_cases.md) - Problem-solving approaches

#### **DevOps/SysAdmins** 
- [Setup](./setup.md) - Installation and configuration
- [Running](./running.md) - Deployment and operations
- [Troubleshooting](./troubleshooting.md) - Issue resolution

#### **Architects**
- [Overview](./overview.md) - System architecture
- [Future](./future.md) - Scalability and evolution
- [Guidelines](./guidelines.md) - Design patterns

#### **Maintainers**
- [Update Docs](./update_docs.md) - Documentation maintenance
- [Future](./future.md) - Roadmap and planning
- [Testing](./testing.md) - Quality assurance

### By Topic

#### **AI Models & Processing**
- [Overview](./overview.md#core-components) - Processing pipeline
- [Setup](./setup.md#download-ai-model-weights) - Model installation
- [Troubleshooting](./troubleshooting.md#ai-model-loading-issues) - Model debugging

#### **Database Operations**
- [Overview](./overview.md#data-layer) - Database architecture  
- [Guidelines](./guidelines.md#repository-pattern-implementation) - Data access patterns
- [Troubleshooting](./troubleshooting.md#database-and-storage-issues) - Database issues

#### **Search & Embeddings**
- [Overview](./overview.md#query-layer) - Search architecture
- [Future](./future.md#search-performance) - Search optimization
- [Thinking Cases](./thinking_cases.md#edge-case-handling-strategies) - Search edge cases

#### **Performance & Scaling**
- [Future](./future.md#performance-optimization-roadmap) - Performance roadmap
- [Troubleshooting](./troubleshooting.md#performance-issues) - Performance debugging
- [Thinking Cases](./thinking_cases.md#case-study-performance-optimization-decision) - Optimization decisions

## Key Concepts

### Architecture Patterns
- **Repository Pattern**: Database abstraction layer
- **Model Interface**: Standardized AI model integration  
- **Dependency Injection**: Service composition
- **Event-Driven Processing**: Async pipeline management

### Core Technologies
- **FastAPI**: REST API framework
- **SQLite**: Metadata storage
- **Qdrant**: Vector embeddings database
- **Redis/RabbitMQ**: Task queue management
- **YOLO/CLIP/BLIP**: AI models for detection/embedding/description

### Data Flow
1. **Ingestion**: File system monitoring
2. **Queueing**: Async processing pipeline
3. **Processing**: AI model inference
4. **Storage**: Metadata + embeddings storage
5. **Search**: Semantic query processing

## Development Workflow

### For New Features
1. Review [Guidelines](./guidelines.md#architecture-patterns) for patterns
2. Check [Future](./future.md) for alignment with roadmap
3. Follow [Testing](./testing.md) strategy for coverage
4. Use [Thinking Cases](./thinking_cases.md) for decision-making
5. Update relevant documentation per [Update Docs](./update_docs.md)

### For Bug Fixes
1. Start with [Troubleshooting](./troubleshooting.md) for known issues
2. Apply [Thinking Cases](./thinking_cases.md#debugging-methodology) framework
3. Test fix using [Testing](./testing.md) procedures
4. Update troubleshooting guide if new issue pattern

### For Performance Issues
1. Use [Troubleshooting](./troubleshooting.md#performance-issues) diagnostics
2. Apply [Thinking Cases](./thinking_cases.md#case-study-performance-optimization-decision) process
3. Consider [Future](./future.md#performance-optimization-roadmap) strategies
4. Document findings for future reference

## Documentation Maintenance

This documentation is designed to evolve with the codebase. Each file:

- **Stays focused**: Single concern per file
- **Stays current**: Updated with code changes
- **Stays concise**: Under 300 lines for optimal chunking
- **Cross-references**: Links to related information
- **Provides examples**: Runnable commands and code snippets

See [Update Docs](./update_docs.md) for detailed maintenance procedures.

## Getting Help

### Quick Help by Issue Type
- **Installation problems** → [Setup](./setup.md) → [Troubleshooting](./troubleshooting.md#service-connection-failures)
- **Processing failures** → [Troubleshooting](./troubleshooting.md#processing-pipeline-issues) → [Thinking Cases](./thinking_cases.md#edge-case-handling-strategies)
- **Performance issues** → [Troubleshooting](./troubleshooting.md#performance-issues) → [Future](./future.md#performance-optimization-roadmap)
- **Search not working** → [Troubleshooting](./troubleshooting.md#search-returns-no-results) → [Overview](./overview.md#query-layer)

### Diagnostic Commands
```bash
# Quick system health check
docker-compose ps
curl -f http://localhost:8000/docs
redis-cli ping
curl -f http://localhost:6333/collections

# Check processing status
sqlite3 pixquery.db "SELECT COUNT(*) as total, SUM(processed) as processed FROM images;"

# Monitor processing
rq info --url redis://localhost:6379
docker-compose logs -f --tail=20
```

### Log Analysis
```bash
# Find recent errors
grep -i "error\|exception" errors.log | tail -10

# Check AI model issues  
grep -i "cuda\|model\|loading" errors.log

# Database connection problems
grep -i "database\|sqlite\|lock" errors.log
```

This documentation serves as both a reference guide and an operational handbook for effectively working with the PixQuery backend system.