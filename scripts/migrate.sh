#!/bin/bash
# migrate.sh - Database migration script for updates

set -e

echo "=========================================="
echo "AI Agent Migration Script"
echo "=========================================="

# Check if we need to migrate
if [ ! -f "data/migration-version.txt" ]; then
    CURRENT_VERSION="0.0.0"
else
    CURRENT_VERSION=$(cat data/migration-version.txt)
fi

TARGET_VERSION="1.0.0"

echo "Current version: $CURRENT_VERSION"
echo "Target version: $TARGET_VERSION"

if [ "$CURRENT_VERSION" = "$TARGET_VERSION" ]; then
    echo "✅ Already at target version, no migration needed"
    exit 0
fi

echo "🔄 Starting migration from $CURRENT_VERSION to $TARGET_VERSION..."

# Version-specific migrations
case "$CURRENT_VERSION" in
    "0.0.0"|"0.1.0")
        echo "Applying migration 0.x → 1.0.0..."
        
        # Create necessary directories
        mkdir -p data/chroma data/redis workspace logs
        
        # Update ChromaDB configuration if exists
        if [ -f "config/chromadb_config.json" ]; then
            echo "Updating ChromaDB config..."
            jq '.persist_directory = "/chroma/chroma"' config/chromadb_config.json > tmp.json && mv tmp.json config/chromadb_config.json
        fi
        
        # Update version
        echo "$TARGET_VERSION" > data/migration-version.txt
        ;;
        
    *)
        echo "⚠️  Unknown version, performing full migration..."
        # Backup data
        ./scripts/backup.sh
        
        # Clean and start fresh
        docker compose down -v
        rm -rf data/* workspace/* logs/*
        
        # Update version
        echo "$TARGET_VERSION" > data/migration-version.txt
        ;;
esac

echo "✅ Migration complete!"
echo "New version: $(cat data/migration-version.txt)"   