# Rule: Always Map Columns by Header Name (Dynamic Header Scanner)

## Core Requirement
When reading, writing, or exporting data from/to Google Sheets or Excel:
1. **NEVER use hardcoded column indexes** (e.g. `row[3]`, `col 5`).
2. **ALWAYS scan Row 1 and Row 2 headers dynamically** and map fields based on exact header names or recognized aliases.
3. **Strict QA Gate**: If required column headers are missing from the sheet, raise explicit warnings instead of writing to wrong columns.
