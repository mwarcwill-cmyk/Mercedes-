from collections import defaultdict, deque
import json
import os
import random
import time
from urllib.parse import urlparse
from telegram import ChatPermissions, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==================== CONFIGURATION ====================
TOKEN = "8855187717:AAG9lm5Z-yOzV65dlEbfqvU051ItBbow9LM"
SPAM_WINDOW = 8  # Seconds
SPAM_COUNT = 4  # Messages allowed in window
REPEAT_N = 3  # Identical consecutive messages limit
MUTE_DURATION = 3 * 60 * 60  # 3 hours in seconds for spam
INVITES_PROMOTE_THRESHOLD = 5  # Invites required for admin promotion

# Allowed external links whitelist
ALLOWED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "github.com",
    "google.com",
    "wikipedia.org",
}

# Chat triggers and their corresponding responses (Oakland style)
TRIGGERS = {
    "mercedes": "I run town business for my lord Gotti on errthang. Anyone else pulling up running their jaws is just dummy loud.",
    "keeb": "on momma's, that nigga love playing with boy butt heavy.",
}

# Owner username trigger options (Gotti)
OWNER_USERNAME = "thugginhard6630"
OWNER_WORSHIP_PHRASES = [
    "on citas, yes daddy mane 😘",
    "on errthang, whatever you say my big homie 👑",
    "at your command, boss man~",
    "on momma's, real town business right here",
]

# ==================== STATE & DATABASE TRACKERS ====================
hits = defaultdict(deque)
last_text = defaultdict(lambda: ("", 0))
afk_users = set()

DATA_FILE = "user_data.json"
INVITES_FILE = "invites.json"


def load_json_file(filename):
  """Loads data from a json file."""
  if os.path.exists(filename):
    try:
      with open(filename, "r") as f:
        return json.load(f)
    except Exception:
      pass
  return {}


def save_json_file(filename, data):
  """Saves data to a json file."""
  try:
    with open(filename, "w") as f:
      json.dump(data, f, indent=4)
  except Exception:
    pass


user_data = load_json_file(DATA_FILE)
invite_data = load_json_file(INVITES_FILE)

# ==================== HELPER FUNCTIONS ====================


def get_user_stats(user_id: int, username: str):
  """Gets or initializes stats for a user."""
  uid_str = str(user_id)
  if uid_str not in user_data:
    user_data[uid_str] = {"money": 100, "username": username or "Unknown"}
    save_json_file(DATA_FILE, user_data)
  return user_data[uid_str]


def get_user_invites(user_id: int):
  """Gets invite count for a user."""
  uid_str = str(user_id)
  if uid_str not in invite_data:
    invite_data[uid_str] = {"count": 0, "invited_users": []}
  return invite_data[uid_str]


def is_telegram_url(url: str) -> bool:
  """Checks if a URL points to Telegram."""
  try:
    parsed = urlparse(url if "://" in url else "http://" + url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
      domain = domain[4:]
    telegram_domains = {"t.me", "telegram.me", "telegram.dog", "telegra.ph"}
    return domain in telegram_domains or any(
        domain.endswith("." + d) for d in telegram_domains
    )
  except Exception:
    return False


async def contains_forbidden_link(msg) -> bool:
  """Inspects message text/captions and entities for Telegram links."""
  text = msg.text or msg.caption or ""
  all_urls = []

  entities = msg.entities or msg.caption_entities or []
  for entity in entities:
    if entity.type == "url":
      all_urls.append(text[entity.offset : entity.offset + entity.length])
    elif entity.type == "text_link":
      all_urls.append(entity.url)

  for url in all_urls:
    if is_telegram_url(url):
      return True

  return False


def is_spam(uid: int, text: str) -> bool:
  """Tracks message frequency and identical repetition per user."""
  now = time.time()
  q = hits[uid]
  q.append(now)

  while q and now - q[0] > SPAM_WINDOW:
    q.popleft()

  prev, n = last_text[uid]
  if text == prev:
    last_text[uid] = (text, n + 1)
  else:
    last_text[uid] = (text, 1)

  return len(q) >= SPAM_COUNT or last_text[uid][1] >= REPEAT_N


# ==================== COMMAND HANDLERS ====================


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Explains the rules and craps table gameplay in Oakland slang."""
  if not update.message:
    return

  rules_text = (
      "🎲 <b>MERCEDIA'S TOWN CRAPS & RULES</b> 🎰\n\n"
      "1️⃣ <b>No Fed Activity / Spam Links:</b> Drop weird links or act bogus on errthang, and Mercedes"
      " is clearing your message and putting you on the porch for 3 hours straight.\n\n"
      "2️⃣ <b>Town Craps Commands:</b> Roll the bones and stack your paper right!\n"
      "   • /craps <amount> pass (Win on 7 or 11; Don't get caught slipping on 2, 3, 12)\n"
      "   • /craps <amount> field (Hit big on the field action)\n"
      "   • /stats (Check your paper stack)\n"
      "   • /invites (Check how many solid heads you pulled in)\n\n"
      f"3️⃣ <b>How to Get Town Admin:</b> Pull up with your whole mob! Get <b>{INVITES_PROMOTE_THRESHOLD} solid invites</b>,"
      " and Mercedes will automatically slide you the keys to Admin with <b>Voice Chat</b> drop-in rights! 🎙️✨"
  )

  await update.message.reply_text(rules_text, parse_mode="HTML")


async def invites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Checks user invite count."""
  user = update.effective_user
  if not user or not update.message:
    return

  inv_stats = get_user_invites(user.id)
  count = inv_stats["count"]
  await update.message.reply_text(
      f"🎟️ <b>Town Invites Check</b>\n👤 Head: {user.first_name}\n📨 Pull-ups:"
      f" {count} / {INVITES_PROMOTE_THRESHOLD} to Town Admin",
      parse_mode="HTML",
  )


async def craps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Allows users to play a game of Craps."""
  message = update.message
  user = update.effective_user
  chat = update.effective_chat

  if not message or not user or chat.type == "private":
    return

  if len(context.args) < 2:
    await message.reply_text("Usage: /craps <amount> <pass/field>\nExample: /craps 50 pass")
    return

  try:
    bet = int(context.args[0])
  except ValueError:
    await message.reply_text("Put a real number down, dummy.")
    return

  bet_type = context.args[1].lower()
  if bet_type not in ["pass", "field"]:
    await message.reply_text("Stop playing bogus. Choose either 'pass' or 'field'.")
    return

  stats = get_user_stats(user.id, user.first_name)

  if bet <= 0:
    await message.reply_text("You gotta bet a real stack, goofy.")
    return

  if stats["money"] < bet:
    await message.reply_text(f"Man you flat broke on citas! You only got ${stats['money']} to your name.")
    return

  # Roll two dice for Craps
  die1 = random.randint(1, 6)
  die2 = random.randint(1, 6)
  total = die1 + die2

  won = False
  if bet_type == "pass":
    if total in [7, 11]:
      won = True
    elif total in [2, 3, 12]:
      won = False
    else:
      won = random.choice([True, False])
  elif bet_type == "field":
    if total in [2, 3, 4, 9, 10, 11, 12]:
      won = True
    else:
      won = False

  if won:
    winnings = bet
    stats["money"] += winnings
    save_json_file(DATA_FILE, user_data)
    await message.reply_text(
        f"🎲 <b>CRAZY DICE:</b> [{die1} + {die2}] = <b>{total}</b> ({bet_type.upper()} play)\n"
        f"🔥 <b>YOU WENT OFF ON ERRTHANG!</b> Bag secured: +${winnings}\n"
        f"💰 Paper stack: ${stats['money']}",
        parse_mode="HTML",
    )
  else:
    stats["money"] -= bet
    save_json_file(DATA_FILE, user_data)
    await message.reply_text(
        f"🎲 <b>CRAZY DICE:</b> [{die1} + {die2}] = <b>{total}</b> ({bet_type.upper()} play)\n"
        f"❌ <b>HOUSE TOOK IT ALL!</b> Lost: -${bet}\n"
        f"💰 Paper stack: ${stats['money']}",
        parse_mode="HTML",
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Checks current wallet balance."""
  user = update.effective_user
  if not user or not update.message:
    return

  stats = get_user_stats(user.id, user.first_name)
  await update.message.reply_text(
      f"📊 <b>Town Paper Stack</b>\n👤 Head: {user.first_name}\n💰 Cash: ${stats['money']}",
      parse_mode="HTML",
  )


async def toggle_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Toggles AFK screening mode on or off."""
  user = update.effective_user
  if not user or not update.message:
    return

  command = update.message.text.split()[0].lower()

  if "/afk" in command:
    afk_users.add(user.id)
    await message.reply_text(
        "Mercedes got your back covered on momma's. AFK mode: ON, stop hitting your phone."
    )
  elif "/back" in command:
    afk_users.discard(user.id)
    await message.reply_text(
        "Welcome back to the block! AFK mode: OFF, Mercedes stepping down."
    )


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Allows group admins to manually lift a mute early via reply or user ID."""
  if not update.effective_user or not update.message:
    return

  chat = update.effective_chat
  message = update.message
  member = await chat.get_member(update.effective_user.id)

  if member.status not in ("administrator", "creator"):
    await message.reply_text(
        "You ain't got the rank to run this command."
    )
    return

  target_uid = None

  if message.reply_to_message and message.reply_to_message.from_user:
    target_uid = message.reply_to_message.from_user.id
  elif context.args:
    try:
      target_uid = int(context.args[0])
    except ValueError:
      await message.reply_text("Reply to them or drop a valid user ID, dummy.")
      return
  else:
    await message.reply_text("Usage: Reply to a dummy with /unmute or use /unmute <id>")
    return

  try:
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )
    await chat.restrict_member(target_uid, permissions)
    hits.pop(target_uid, None)
    last_text.pop(target_uid, None)
    await message.reply_text(f"Unmuted user {target_uid} on citas. Don't act goofy again.")
  except Exception as e:
    await message.reply_text(f"Couldn't unmute them: {e}")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Allows admins or owner to ban a user by replying or using ID."""
  message = update.message
  user = update.effective_user
  chat = update.effective_chat

  if not message or not user or chat.type == "private":
    return

  try:
    member = await chat.get_member(user.id)
    if member.status not in ("administrator", "creator"):
      await message.reply_text("You ain't got the rank for that.")
      return
  except Exception:
    return

  target_user = None

  if message.reply_to_message and message.reply_to_message.from_user:
    target_user = message.reply_to_message.from_user
  elif context.args:
    try:
      uid = int(context.args[0])
      member_obj = await chat.get_member(uid)
      target_user = member_obj.user
    except Exception:
      pass

  if not target_user:
    await message.reply_text("Reply to someone or drop their ID to get them outta here.")
    return

  if target_user.id == user.id:
    await message.reply_text("You can't ban yourself, goofy.")
    return

  try:
    await chat.ban_member(target_user.id)
    await message.reply_text(
        f"🔨 <b>{target_user.mention_html()}</b> got bounced straight off the block on errthang.",
        parse_mode="HTML",
    )
  except Exception as e:
    await message.reply_text(f"Failed to ban them: {e}")


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Greets new members when they join the group with custom welcome lines."""
  chat = update.effective_chat
  message = update.message
  
  if not message or not message.new_chat_members:
    return

  for new_user in message.new_chat_members:
    if new_user.is_bot:
      continue
    
    welcome_text = (
        f"welcome to my lord gottis chat, {new_user.mention_html()}! 🎉 stay solid and don't act goofy on momma's."
    )
    await chat.send_message(welcome_text, parse_mode="HTML")


async def award_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Manual command for admin to credit an invite to a user: /addinvite"""
  message = update.message
  user = update.effective_user
  chat = update.effective_chat

  if not message or not user:
    return

  try:
    member = await chat.get_member(user.id)
    if member.status not in ("administrator", "creator"):
      return
  except Exception:
    return

  if not message.reply_to_message or not message.reply_to_message.from_user:
    await message.reply_text("Reply to the head who brought someone in with /addinvite")
    return

  target_user = message.reply_to_message.from_user
  inv_stats = get_user_invites(target_user.id)
  inv_stats["count"] += 1
  save_json_file(INVITES_FILE, invite_data)

  await message.reply_text(
      f"📨 Pull-up credited to {target_user.mention_html()}! Total: {inv_stats['count']} / {INVITES_PROMOTE_THRESHOLD}",
      parse_mode="HTML"
  )

  if inv_stats["count"] >= INVITES_PROMOTE_THRESHOLD:
    try:
      member = await chat.get_member(target_user.id)
      if member.status not in ("administrator", "creator"):
        await chat.promote_member(
            target_user.id,
            can_manage_voice_chats=True,
            can_delete_messages=False,
            can_invite_users=True,
        )
        await chat.send_message(
            f"🎉 On errthang! {target_user.mention_html()} brought in {INVITES_PROMOTE_THRESHOLD}"
            " heads and just got bumped to Admin with **Voice Chat** rights on citas! 🎙️",
            parse_mode="HTML",
        )
    except Exception as e:
      print(f"Failed to promote user: {e}")


# ==================== MESSAGE HANDLER ====================


async def on_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Core message listener for triggers, link filtering, and anti-spam."""
  msg = update.effective_message
  chat = update.effective_chat
  user = update.effective_user

  if not msg or not user or chat.type == "private" or user.is_bot:
    return

  text = (msg.text or msg.caption or "").strip()
  if not text:
    return

  text_lower = text.lower()

  # 1. OWNER SPECIAL TRIGGER CHECK (@Thugginhard6630 / Gotti)
  if user.username and user.username.lower() == OWNER_USERNAME:
    if "mercedes" in text_lower:
      worship_response = random.choice(OWNER_WORSHIP_PHRASES)
      await msg.reply_text(worship_response)
      return

  # 2. ADMIN BEGGING TRIGGER CHECK
  if (
      "gotti get give me admin" in text_lower
      or "where's my admin" in text_lower
      or "gotti where's my admin" in text_lower
      or "can i get admin" in text_lower
  ):
    await msg.reply_text("where's yo job at nigga on momma's")
    return

  # 3. Standard Custom Chat Triggers
  for keyword, response in TRIGGERS.items():
    if keyword in text_lower:
      await msg.reply_text(response)
      return

  # 4. AFK Screening Trigger
  if "gotti" in text_lower and afk_users:
    await msg.reply_text(
        "he don't feel like messing with you right now dummy, I'm holding down the line on citas"
    )
    return

  # 5. Bypass checks for group admins/creators
  try:
    member = await chat.get_member(user.id)
    if member.status in ("administrator", "creator"):
      return
  except Exception:
    pass

  # 6. Anti-Spam & Telegram Link Detection
  has_telegram_spam = await contains_forbidden_link(msg)
  is_frequent_spam = is_spam(user.id, text)

  if not (has_telegram_spam or is_frequent_spam):
    return

  punishment_msg = "fuck yo mama u dork on errthang"

  try:
    await msg.delete()

    until_date = int(time.time() + MUTE_DURATION)
    permissions = ChatPermissions(can_send_messages=False)
    await chat.restrict_member(user.id, permissions, until_date=until_date)

    reason_note = (
        "(Muted for 3 hours: weird link activity)"
        if has_telegram_spam
        else "(Muted for 3 hours: spamming the chat)"
    )

    await chat.send_message(
        f"{user.mention_html()} {punishment_msg} *{reason_note}*",
        parse_mode="HTML",
    )
  except Exception:
    await msg.reply_text(
        f"{punishment_msg} (Note: Couldn't mute them, check bot permissions.)"
    )


# ==================== MAIN APPLICATION ====================


def main():
  app = Application.builder().token(TOKEN).build()

  # Register handlers
  app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_msg))
  app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
  app.add_handler(CommandHandler("rules", rules_command))
  app.add_handler(CommandHandler("unmute", unmute))
  app.add_handler(CommandHandler("ban", ban_command))
  app.add_handler(CommandHandler("addinvite", award_invite))
  app.add_handler(CommandHandler("invites", invites_command))
  app.add_handler(CommandHandler("afk", toggle_afk))
  app.add_handler(CommandHandler("back", toggle_afk))
  app.add_handler(CommandHandler("craps", craps_command))
  app.add_handler(CommandHandler("stats", stats_command))

  print("Mercedes is locked in on town business, craps tables hot!")
  app.run_polling()


if __name__ == "__main__":
  main()
