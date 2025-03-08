#!/bin/bash
# Create necessary directories
mkdir -p /opt/render/project/src/data
mkdir -p /opt/render/project/src/static/uploads

# Set permissions
chmod 777 /opt/render/project/src/data
chmod 777 /opt/render/project/src/static/uploads

# Start the keep-alive script in the background
python keep_alive.py &

# Check if database file exists
DB_FILE="/opt/render/project/src/data/shipments.db"
echo "Checking if database exists at: $DB_FILE"
if [ -f "$DB_FILE" ]; then
    echo "Database already exists, skipping initialization"
else
    echo "Database not found, initializing..."
    # Initialize database (creating tables and admin user)
    python -c "from app import create_tables; create_tables()"
fi

# Start the application
gunicorn app:app --config gunicorn_config.py 