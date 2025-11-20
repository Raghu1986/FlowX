DataFlow Validator

Asynchronous Excel/CSV Validation Engine with S3, Redis Streams, WebSockets & Audit Logging

Overview
DataFlow Validator is a high-performance FastAPI-based ingestion and validation engine designed for enterprise-scale workflows. 
It ingests Excel/CSV files, validates them using a rule-based engine, and produces fully annotated Excel outputs, JSON results, 
audit logs, WebSocket progress, and Redis Stream events.

Features:
- Excel & CSV Validation
- Async chunked pipeline
- WebSocket real-time updates
- Redis Stream event broadcasting
- Background task processing
- Azure AD & Cognito authentication
- Rich logging with correlation IDs
- Daily log rotation
- Admin log tailing + streaming endpoints