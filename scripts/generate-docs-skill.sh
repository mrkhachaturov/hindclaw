#!/bin/bash
set -e

# Generate agent skill from HindClaw documentation
# Converts hindclaw-docs/ to skills/hindclaw-docs/ for AI agent consumption.
#
# Ported from upstream vectorize-io/hindsight scripts/generate-docs-skill.sh.
# Differences from upstream:
#   - Preserves the hand-written skills/hindclaw-docs/SKILL.md (backed up
#     before the skill dir is wiped, restored afterwards). If no existing
#     SKILL.md is present, falls back to writing a minimal skeleton.
#   - hindclaw-docs/src/pages/ and hindclaw-docs/examples/ are optional:
#     they are skipped cleanly with a warning if absent.
#   - No CodeSnippet inlining — HindClaw docs don't use the upstream
#     "import raw-loader" pattern, so the conversion only strips MDX
#     imports/JSX and rewrites Docusaurus absolute links.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DOCS_DIR="$ROOT_DIR/hindclaw-docs/docs"
PAGES_DIR="$ROOT_DIR/hindclaw-docs/src/pages"
EXAMPLES_DIR="$ROOT_DIR/hindclaw-docs/examples"
SKILL_DIR="$ROOT_DIR/skills/hindclaw-docs"
REFS_DIR="$SKILL_DIR/references"
SKILL_MD="$SKILL_DIR/SKILL.md"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_info "Generating HindClaw documentation skill..."

# Preserve hand-written SKILL.md across the wipe
SKILL_MD_BACKUP=""
if [ -f "$SKILL_MD" ]; then
    SKILL_MD_BACKUP="$(mktemp)"
    cp "$SKILL_MD" "$SKILL_MD_BACKUP"
    print_info "Backed up existing SKILL.md to preserve hand-written content"
fi

# Clean and recreate skill directory
rm -rf "$SKILL_DIR"
mkdir -p "$REFS_DIR"

# Convert MDX to Markdown by stripping JSX-specific imports and components.
# HindClaw docs use Docusaurus 3.x conventions matching upstream, so the
# same rules apply. No CodeSnippet inlining because HindClaw docs do not
# use the raw-loader pattern.
convert_mdx_to_md() {
    local src="$1"
    local dest="$2"

    python3 - "$src" "$dest" <<'PYTHON'
import sys
import re
from pathlib import Path

src_file = Path(sys.argv[1])
dest_file = Path(sys.argv[2])

content = src_file.read_text()

# Remove frontmatter
content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

# Remove import statements
content = re.sub(r'^import .*?;?\n', '', content, flags=re.MULTILINE)

# Convert <Tabs> to markdown sections
content = re.sub(r'<Tabs>\s*', '', content)
content = re.sub(r'</Tabs>\s*', '', content)

# Convert <TabItem value="x" label="Y"> to ### Y
content = re.sub(r'<TabItem value="[^"]*" label="([^"]+)">', r'### \1\n', content)
content = re.sub(r'</TabItem>', '', content)

# Convert :::tip, :::warning, :::note to markdown blockquotes
content = re.sub(r':::tip (.+?)\n', r'> **TIP: \1**\n> \n', content)
content = re.sub(r':::warning (.+?)\n', r'> **WARNING: \1**\n> \n', content)
content = re.sub(r':::note (.+?)\n', r'> **NOTE: \1**\n> \n', content)
content = re.sub(r':::\s*\n', '', content)

# Clean up extra blank lines
content = re.sub(r'\n{3,}', '\n\n', content)

dest_file.write_text(content)
PYTHON
}

# Process a single markdown file: convert or copy into references/
process_file() {
    local src_file="$1"
    local rel_path="${src_file#$DOCS_DIR/}"
    local dest_file="$REFS_DIR/$rel_path"

    mkdir -p "$(dirname "$dest_file")"

    if [[ "$src_file" == *.mdx ]]; then
        dest_file="${dest_file%.mdx}.md"
        print_info "Converting: $rel_path"
        convert_mdx_to_md "$src_file" "$dest_file"
    else
        print_info "Copying: $rel_path"
        cp "$src_file" "$dest_file"
    fi
}

# Walk the docs tree
print_info "Processing documentation files..."
if [ -d "$DOCS_DIR" ]; then
    find "$DOCS_DIR" -type f \( -name "*.md" -o -name "*.mdx" \) | while read -r file; do
        process_file "$file"
    done
else
    print_warn "Docs directory not found at $DOCS_DIR — skipping"
fi

# Process standalone pages from src/pages/ — optional
if [ -d "$PAGES_DIR" ]; then
    print_info "Processing standalone pages..."
    for page in best-practices faq; do
        for ext in md mdx; do
            src="$PAGES_DIR/$page.$ext"
            if [ -f "$src" ]; then
                dest="$REFS_DIR/$page.md"
                mkdir -p "$(dirname "$dest")"
                if [[ "$src" == *.mdx ]]; then
                    convert_mdx_to_md "$src" "$dest"
                else
                    cp "$src" "$dest"
                fi
                print_info "Included page: $page.$ext"
            fi
        done
    done

    # Changelog may be a single file or a directory
    if [ -f "$PAGES_DIR/changelog.md" ] || [ -f "$PAGES_DIR/changelog.mdx" ]; then
        for ext in md mdx; do
            src="$PAGES_DIR/changelog.$ext"
            if [ -f "$src" ]; then
                dest="$REFS_DIR/changelog.md"
                mkdir -p "$(dirname "$dest")"
                if [[ "$src" == *.mdx ]]; then
                    convert_mdx_to_md "$src" "$dest"
                else
                    cp "$src" "$dest"
                fi
                print_info "Included page: changelog.$ext"
            fi
        done
    elif [ -d "$PAGES_DIR/changelog" ]; then
        find "$PAGES_DIR/changelog" -type f \( -name "*.md" -o -name "*.mdx" \) | while read -r file; do
            rel="${file#$PAGES_DIR/}"
            dest="$REFS_DIR/$rel"
            if [[ "$file" == *.mdx ]]; then
                dest="${dest%.mdx}.md"
            fi
            mkdir -p "$(dirname "$dest")"
            if [[ "$file" == *.mdx ]]; then
                convert_mdx_to_md "$file" "$dest"
            else
                cp "$file" "$dest"
            fi
            print_info "Included changelog: ${file#$PAGES_DIR/changelog/}"
        done
    fi
else
    print_warn "Pages directory not found at $PAGES_DIR — skipping standalone pages"
fi

# Examples directory — optional; currently unused by HindClaw docs
if [ ! -d "$EXAMPLES_DIR" ]; then
    print_warn "Examples directory not found at $EXAMPLES_DIR — skipping"
fi

# Copy OpenAPI spec into the skill
OPENAPI_SRC="$ROOT_DIR/hindclaw-docs/static/openapi.json"
if [ -f "$OPENAPI_SRC" ]; then
    cp "$OPENAPI_SRC" "$REFS_DIR/openapi.json"
    print_info "Included: openapi.json"
else
    print_warn "openapi.json not found at $OPENAPI_SRC — skipping"
fi

# Restore or generate SKILL.md
if [ -n "$SKILL_MD_BACKUP" ] && [ -f "$SKILL_MD_BACKUP" ]; then
    cp "$SKILL_MD_BACKUP" "$SKILL_MD"
    rm -f "$SKILL_MD_BACKUP"
    print_info "Restored hand-written SKILL.md"
else
    print_warn "No existing SKILL.md found — writing minimal skeleton"
    cat > "$SKILL_MD" <<'EOF'
---
name: hindclaw-docs
description: HindClaw documentation for AI agents. Use to learn about HindClaw access control, API, configuration, and integration.
---

# HindClaw Documentation Skill

Technical documentation for HindClaw — the access-control and policy layer
on top of Hindsight.

## When to Use This Skill

Use this skill when you need to:
- Understand HindClaw architecture and access control model
- Configure policies, groups, and service accounts
- Set up the HindClaw server
- Integrate via the Terraform provider or API
- Review API endpoints and parameters

## Documentation Structure

All documentation is in `references/` organized by category. Use Glob
to find files and Grep to search content.

---

**Auto-generated skeleton** — replace with hand-written content. Run
`./scripts/generate-docs-skill.sh` to regenerate references while
preserving this file.
EOF
fi

print_info "Generated skill at: $SKILL_DIR"
print_info "Documentation files: $(find "$REFS_DIR" -type f | wc -l | tr -d ' ')"

# Rewrite Docusaurus absolute paths (e.g. /guides/foo) to relative paths
print_info "Rewriting Docusaurus absolute paths to relative paths..."
python3 - "$REFS_DIR" <<'PYTHON'
import sys
import re
import os
from pathlib import Path

refs_dir = Path(sys.argv[1]).resolve()
link_pattern = re.compile(r'\[([^\]]*)\]\((/[^)]*)\)')

SPECIAL_MAPPINGS = {
    '/api-reference': 'openapi.json',
}

def try_resolve(url_path, refs_dir):
    """Find the file in refs_dir for a Docusaurus absolute path like /guides/foo."""
    if url_path in SPECIAL_MAPPINGS:
        candidate = refs_dir / SPECIAL_MAPPINGS[url_path]
        return candidate if candidate.exists() else None
    doc_path = url_path.lstrip('/')
    for candidate in [
        refs_dir / (doc_path + '.md'),
        refs_dir / doc_path / 'index.md',
        refs_dir / doc_path,
    ]:
        if candidate.exists():
            return candidate
    return None

image_pattern = re.compile(r'!\[[^\]]*\]\([^)]*\)')
html_img_pattern = re.compile(r'<img\b[^>]*/?>', re.IGNORECASE)

changed = 0
for md_file in refs_dir.rglob("*.md"):
    original_content = md_file.read_text()

    # Strip images (markdown and HTML)
    content = image_pattern.sub('', original_content)
    content = html_img_pattern.sub('', content)

    def rewrite(match):
        text = match.group(1)
        url = match.group(2)
        anchor = ''
        if '#' in url:
            url, frag = url.split('#', 1)
            anchor = '#' + frag
        if not url or url == '/':
            return text  # strip link, keep text
        resolved = try_resolve(url, refs_dir)
        if resolved is None:
            return text  # strip unresolvable link, keep text
        rel = os.path.relpath(resolved, md_file.parent)
        return f'[{text}]({rel}{anchor})'

    new_content = link_pattern.sub(rewrite, content)
    if new_content != original_content:
        md_file.write_text(new_content)
        changed += 1

print(f"[INFO] Rewrote Docusaurus links in {changed} file(s)")
PYTHON

# Validate: no links point outside the skill directory
print_info "Validating links in generated skill files..."
python3 - "$SKILL_DIR" <<'PYTHON'
import sys
import re
from pathlib import Path

skill_dir = Path(sys.argv[1]).resolve()
errors = []

link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

for md_file in skill_dir.rglob("*.md"):
    content = md_file.read_text()
    for match in link_pattern.finditer(content):
        url = match.group(2).split("#")[0].strip()
        if not url:
            continue
        if url.startswith(("http://", "https://", "mailto:", "ftp://")):
            continue
        resolved = (md_file.parent / url).resolve()
        if not str(resolved).startswith(str(skill_dir)):
            errors.append(f"  {md_file.relative_to(skill_dir)}: '{url}' -> {resolved}")

if errors:
    print("ERROR: The following links point outside the skill directory.")
    print("All links must be absolute URLs or relative paths within the skill.")
    for e in errors:
        print(e)
    sys.exit(1)

print(f"[INFO] Link validation passed ({skill_dir})")
PYTHON

echo ""
print_info "Usage:"
echo "  - Agents can use Glob to find files: references/guides/*.md"
echo "  - Agents can use Grep to search content: pattern='policy'"
echo "  - Agents can use Read to view full docs"
