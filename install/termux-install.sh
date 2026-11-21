#!/data/data/com.termux/files/usr/bin/bash
# omnireach-remote — Termux installer (Android)
# A-tier channels only: forums, Discourse, Reddit archive, Zhihu API,
# arXiv/OpenAlex, RSS, GitHub. No browser/cookie channels.
set -euo pipefail

REPO="felicagodfrey2771995wpb-hub/omnireach-skill"
SRC_DIR="$HOME/omnireach-skill"
SKILL_DIR="$SRC_DIR/skills/omnireach-remote"
BIN="$PREFIX/bin"

echo "==> Installing packages"
pkg update -y
pkg install -y python git gh

if [ ! -d "$SRC_DIR/.git" ]; then
  echo "==> Cloning $REPO (gh auth login if prompted)"
  gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web
  gh repo clone "$REPO" "$SRC_DIR" -- --depth 1
else
  echo "==> Updating $SRC_DIR"
  git -C "$SRC_DIR" pull --ff-only
fi

echo "==> Linking CLIs into $BIN"
cat > "$BIN/forum-cli" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$SKILL_DIR/scripts/forum-cli/forum_cli.py" "\$@"
EOF
chmod +x "$BIN/forum-cli"

cp "$SKILL_DIR/scripts/discourse-forum" "$BIN/discourse-forum"
chmod +x "$BIN/discourse-forum"

cat > "$BIN/zhihu-search" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$SKILL_DIR/scripts/zhihu-search.py" "\$@"
EOF
chmod +x "$BIN/zhihu-search"

# Optional secrets: drop a .env next to the skill dir (zhihu-search auto-loads it)
ENV_FILE="$SKILL_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<'EOF'
# Optional keys — fill in what you have. Never commit this file.
# ZHIHU_ACCESS_KEY=
# EXA_API_KEY=
# GH_TOKEN=
EOF
fi

cat <<'DONE'

Done. Try:
  forum-cli sites
  forum-cli search v2ex "keyword"
  discourse-forum search archcn "keyword"
  zhihu-search '{"query":"...","count":10}'   # needs ZHIHU_ACCESS_KEY in skills/omnireach-remote/.env
  curl -s "https://r.jina.ai/https://example.com"        # read a page
  curl -s "https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=android&limit=5"

Full routing doc: ~/omnireach-skill/skills/omnireach-remote/SKILL.md
DONE
