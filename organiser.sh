#!/bin/bash

SOURCE_DIR="$1"
DEST_DIR="$2"

if [[ -z "$SOURCE_DIR" || -z "$DEST_DIR" ]]; then
  echo "❌ Usage: $0 <source_directory> <destination_directory>"
  exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
  echo "❌ Source directory does not exist: $SOURCE_DIR"
  exit 1
fi

mkdir -p "$DEST_DIR"

# mapfile -t FILES < <(find "$SOURCE_DIR" -type f ! -name ".*")
FILES=()
while IFS= read -r line; do
  FILES+=("$line")
done < <(find "$SOURCE_DIR" -type f ! -name ".*")

TOTAL=${#FILES[@]}
COUNT=0
BAR_WIDTH=40

for FILE in "${FILES[@]}"; do
  ((COUNT++))

  CREATED=$(stat -f "%SB" -t "%Y-%m-%d" "$FILE" 2>/dev/null)
  [[ -z "$CREATED" ]] && continue

  YEAR=$(date -j -f "%Y-%m-%d" "$CREATED" +"%Y" 2>/dev/null)
  MONTH=$(date -j -f "%Y-%m-%d" "$CREATED" +"%m-%B" 2>/dev/null)
  [[ -z "$YEAR" || -z "$MONTH" ]] && continue

  TARGET_DIR="$DEST_DIR/$YEAR/$MONTH"
  mkdir -p "$TARGET_DIR"
  mv "$FILE" "$TARGET_DIR/"

  # Progress bar
  PERCENT=$((COUNT * 100 / TOTAL))
  FILLED=$((PERCENT * BAR_WIDTH / 100))
  EMPTY=$((BAR_WIDTH - FILLED))
  BAR=$(printf "%${FILLED}s" | tr ' ' '█')$(printf "%${EMPTY}s" | tr ' ' '░')
  printf "\rProgress: [%s] %3d%% (%d/%d)" "$BAR" "$PERCENT" "$COUNT" "$TOTAL"
done

echo -e "\n✅ Done organizing $TOTAL files."