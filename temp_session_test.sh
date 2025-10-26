#!/bin/bash
set -e
curl -s -X POST http://localhost:8000/sessions/ \
  -H 'Content-Type: application/json' \
  -d '{"id":"sess-100","doctor_id":"doc-9","title":"説明テスト","artifact_hash":"abc123"}'
