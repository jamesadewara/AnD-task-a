#!/bin/bash
sudo docker compose up -d --build
echo "Task A started on http://127.0.0.1:8000"
echo "Docs: http://127.0.0.1:8000/docs"
echo "ReDoc: http://127.0.0.1:8000/redoc"