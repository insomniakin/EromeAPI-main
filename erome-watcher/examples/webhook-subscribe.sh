# Example webhook subscription command
# Adjust deliver target for your setup.
hermes webhook subscribe erome-alerts \
  --prompt "{telegram_text}" \
  --description "Receive Erome watcher alerts" \
  --deliver telegram \
  --deliver-chat-id "YOUR_CHAT_ID" \
  --deliver-only
