#!/bin/bash
set -e

EPHEMERIS_DIR="/usr/share/swisseph"
TIMEZONE_DIR="/usr/share/timezonefinder"

echo "🔍 Checking caches..."

# Проверяем эфемериды
if [ ! -f "$EPHEMERIS_DIR/seas_18.se1" ] || [ ! -f "$EPHEMERIS_DIR/semo_18.se1" ]; then
    echo "📥 Downloading SwissEphemeris files..."
    mkdir -p "$EPHEMERIS_DIR"
    cd "$EPHEMERIS_DIR"
    
    for file in seas_18.se1 semo_18.se1 sepl_18.se1 sefstars.txt; do
        if [ ! -f "$file" ]; then
            echo "  Downloading $file..."
            wget -q "https://github.com/aloistr/swisseph/raw/master/ephe/$file"
            if [ $? -ne 0 ]; then
                echo "❌ Failed to download $file"
                exit 1
            fi
        fi
    done
    echo "✅ SwissEphemeris files downloaded"
else
    echo "✅ SwissEphemeris files already present"
fi

# Проверяем timezone data
if [ ! -f "$TIMEZONE_DIR/timezones.geojson.zip" ]; then
    echo "📥 Downloading timezone data..."
    mkdir -p "$TIMEZONE_DIR"
    cd "$TIMEZONE_DIR"
    wget -q https://github.com/evansiroky/timezone-boundary-builder/releases/download/2023d/timezones.geojson.zip
    unzip -q timezones.geojson.zip
    echo "✅ Timezone data downloaded"
else
    echo "✅ Timezone data already present"
fi

# Запускаем основную команду
exec "$@"
