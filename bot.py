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
TOKEN = "8874199870:AAE0Zb3lrTrap3621MPWL-eF0eXBmYTNfCE"
SPAM_WINDOW = 8  # Seconds
SPAM_COUNT = 4  # Messages allowed in window
REPEAT_N = 3  # Identical consecutive messages limit
MUTE_DURATION = 3 * 60 * 60  # 3 hours in seconds for spam
XP_PROMOTE_THRESHOLD = 1500  # XP required for admin promotion

# Allowed external links whitelist
ALLOWED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "github.com",
    "google.com",
    "wikipedia.org",
}

# Chat triggers and their corresponding responses
TRIGGERS = {
    "mercedes": "I work for mr.uchies anybody else talking to me is lummy",
    "dae": "is a whore",
    "keeb": "yk that nigga like boy butt",
}

# Owner username trigger options (Gotti)
OWNER_USERNAME = "thugginhard6630"
OWNER_WORSHIP_PHRASES = [
    "yes daddy😘",
    "yes my lord",
    "at your command, my king 👑",
    "yes master, whatever you say~",
]

# ==================== STATE & DATABASE TRACKERS ====================
hits = defaultdict(deque)
last_text = defaultdict(lambda: ("", 0))
afk_users = set()

DATA_FILE = "user_data.json"


def load_user_data():
  """Loads user money and XP from file."""
  if os.path.exists(DATA_FILE):
    try:
      with open(DATA_FILE, "r") as f:
        return json.load(f)
    except Exception:
      pass
  return {}


def save_user_data(data):
  """Saves user money and XP to file."""
  try:
    with open(DATA_FILE, "w") as f:
      json.dump(data, f, indent=4)
  except Exception:
    pass


user_data = load_user_data()

# ==================== HELPER FUNCTIONS ====================


def get_user_stats(user_id: int, username: str):
  """Gets or initializes stats for a user."""
  uid_str = str(user_id)
  if uid_str not in user_data:
    user_data[uid_str] = {"xp": 0, "money": 100, "username": username or "Unknown"}  # Start with $100 to gamble
  return user_data[uid_str]


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
  """Explains the rules and casino gameplay."""
  if not update.message:
    return

  rules_text = (
      "🎰 <b>MERCEDES CASINO & RULES GUIDE</b> 🎲\n\n"
      "1️⃣ <b>No Spamming / Telegram Links:</b> Drop spam or unauthorized links,"
      " and Mercedes will delete your message and mute you for 3 hours.\n\n"
      "2️⃣ <b>Casino Commands & Gambling:</b> Stack your bag at the tables!\n"
      "   • /dice <amount> (Roll a die: 1-3 is lose, 4-6 doubles your bet!)\n"
      "   • /slots <amount> (Spin the slot machine for massive payouts)\n"
      "   • /stats (Check your current cash and XP wallet)\n\n"
      "3️⃣ <b>How to Get VC Permissions:</b> Hit the jackpot and grind your way up to"
      f" <b>{XP_PROMOTE_THRESHOLD} XP</b> through gambling, and Mercedes"
      " will automatically promote you to an Admin with <b>Voice Chat</b>"
      " permissions! 🎙️✨"
  )

  await update.message.reply_text(rules_text, parse_mode="HTML")


async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Allows users to gamble money on a dice roll."""
  message = update.message
  user = update.effective_user
  chat = update.effective_chat

  if not message or not user or chat.type == "private":
    return

  if not context.args:
    await message.reply_text("Usage: /dice <amount> (e.g., /dice 50)")
    return

  try:
    bet = int(context.args[0])
  except ValueError:
    await message.reply_text("Please enter a valid number for your bet.")
    return

  stats = get_user_stats(user.id, user.first_name)

  if bet <= 0:
    await message.reply_text("You have to bet more than 0, dumbass.")
    return

  if stats["money"] < bet:
    await message.reply_text(f"You're broke! You only have ${stats['money']} in your wallet.")
    return

  roll = random.randint(1, 6)
  
  if roll >= 4:
    winnings = bet
    stats["money"] += winnings
    earned_xp = bet * 2
    stats["xp"] += earned_xp
    save_user_data(user_data)
    await message.reply_text(
        f"🎲 {user.mention_html()} rolled a <b>{roll}</b>!\n"
        f"🎉 <b>YOU WIN!</b> Payout: +${winnings} | ✨ XP: +{earned_xp}\n"
        f"💰 Balance: ${stats['money']}",
        parse_mode="HTML",
    )
  else:
    stats["money"] -= bet
    earned_xp = max(10, bet // 2)
    stats["xp"] += earned_xp
    save_user_data(user_data)
    await message.reply_text(
        f"🎲 {user.mention_html()} rolled a <b>{roll}</b>...\n"
        f"💸 <b>HOUSE WINS!</b> Lost: -${bet} | (At least you got +{earned_xp} XP)\n"
        f"💰 Balance: ${stats['money']}",
        parse_mode="HTML",
    )

  # Check promotion threshold
  await check_promotion(chat, user, stats)


async def slots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Slot machine mini-game."""
  message = update.message
  user = update.effective_user
  chat = update.effective_chat

  if not message or not user or chat.type == "private":
    return

  if not context.args:
    await message.reply_text("Usage: /slots <amount> (e.g., /slots 50)")
    return

  try:
    bet = int(context.args[0])
  except ValueError:
    await message.reply_text("Please enter a valid number for your bet.")
    return

  stats = get_user_stats(user.id, user.first_name)

  if bet <= 0:
    await message.reply_text("Bet a real amount, dummy.")
    return

  if stats["money"] < bet:
    await message.reply_text(f"You don't got the funds! Wallet: ${stats['money']}.")
    return

  fruits = ["🍒", "🍋", "🍊", "🔔", "💎", "7️⃣"]
  spin1 = random.choice(fruits)
  spin2 = random.choice(fruits)
  spin3 = random.choice(fruits)

  slot_display = f"[ {spin1} | {spin2} | {spin3} ]"

  if spin1 == spin2 == spin3:
    multiplier = 10 if spin1 == "7️⃣" else 5
    winnings = bet * multiplier
    stats["money"] += winnings
    earned_xp = winnings * 2
    stats["xp"] += earned_xp
    save_user_data(user_data)
    await message.reply_text(
        f"🎰 {user.mention_html()} spun the slots:\n{slot_display}\n\n"
        f"🔥 <b>JACKPOT! ({multiplier}x)</b> Won: +${winnings} | ✨ XP: +{earned_xp}\n"
        f"💰 Balance: ${stats['money']}",
        parse_mode="HTML",
    )
  elif spin1 == spin2 or spin2 == spin3 or spin1 == spin3:
    winnings = bet
    stats["money"] += winnings
    earned_xp = bet
    stats["xp"] += earned_xp
    save_user_data(user_data)
    await message.reply_text(
        f"🎰 {user.mention_html()} spun the slots:\n{slot_display}\n\n"
        f"✨ <b>Two of a kind!</b> Won: +${winnings} | XP: +{earned_xp}\n"
        f"💰 Balance: ${stats['money']}",
        parse_mode="HTML",
    )
  else:
    stats["money"] -= bet
    earned_xp = 10
    stats["xp"] += earned_xp
    save_user_data(user_data)
    await message.reply_text(
        f"🎰 {user.mention_html()} spun the slots:\n{slot_display}\n\n"
        f"❌ <b>You missed!</b> Lost: -${bet} | XP: +{earned_xp}\n"
        f"💰 Balance: ${stats['money']}",
        parse_mode="HTML",
    )

  await check_promotion(chat, user, stats)


async def check_promotion(chat, user, stats):
  """Checks if user crossed XP threshold for admin promotion."""
  if stats["xp"] >= XP_PROMOTE_THRESHOLD:
    try:
      member = await chat.get_member(user.id)
      if member.status not in ("administrator", "creator"):
        await chat.promote_member(
            user.id,
            can_manage_voice_chats=True,
            can_delete_messages=False,
            can_invite_users=True,
        )
        await chat.send_message(
            f"🎉 Holy shit! {user.mention_html()} hit {XP_PROMOTE_THRESHOLD}"
            " XP at the casino tables and has been promoted to Admin with"
            " **Voice Call** permissions! 🎙️",
            parse_mode="HTML",
        )
    except Exception as e:
      print(f"Failed to promote user: {e}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Checks current XP and wallet balance."""
  user = update.effective_user
  if not user or not update.message:
    return

  stats = get_user_stats(user.id, user.first_name)
  await update.message.reply_text(
      f"📊 <b>Casino Wallet & Stats</b>\n👤 User: {user.first_name}\n💰 Cash:"
      f" ${stats['money']}\n✨ XP: {stats['xp']} / {XP_PROMOTE_THRESHOLD} XP to"
      " Voice Admin",
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
    await update.message.reply_text(
        "Mercedes is now watching your back. AFK mode: ON."
    )
  elif "/back" in command:
    afk_users.discard(user.id)
    await update.message.reply_text(
        "Welcome back! AFK mode: OFF. Mercedes is standing down."
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
        "You don't have permission to use this command."
    )
    return

  target_uid = None

  if message.reply_to_message and message.reply_to_message.from_user:
    target_uid = message.reply_to_message.from_user.id
  elif context.args:
    try:
      target_uid = int(context.args[0])
    except ValueError:
      await message.reply_text("Please reply to a user or provide a valid numeric User ID.")
      return
  else:
    await message.reply_text("Usage: Reply to a user with /unmute or use /unmute <user_id>")
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
    await message.reply_text(f"Successfully unmuted user {target_uid}.")
  except Exception as e:
    await message.reply_text(f"Failed to unmute user: {e}")


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
      await message.reply_text("You don't have permission to use this command.")
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
    await message.reply_text("Usage: Reply to a user's message with /ban or provide their User ID.")
    return

  if target_user.id == user.id:
    await message.reply_text("You can't ban yourself.")
    return

  try:
    await chat.ban_member(target_user.id)
    await message.reply_text(
        f"🔨 <b>{target_user.mention_html()}</b> has been banned from the chat.",
        parse_mode="HTML",
    )
  except Exception as e:
    await message.reply_text(f"Failed to ban user: {e}")


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Greets new members when they join the group."""
  chat = update.effective_chat
  message = update.message
  
  if not message or not message.new_chat_members:
    return

  for new_user in message.new_chat_members:
    if new_user.is_bot:
      continue
    
    welcome_text = (
        f"Welcome to the chat, {new_user.mention_html()}! 🎉 "
        "Glad you made it in. Make sure you behave, check /rules, and hit the casino tables!"
    )
    await chat.send_message(welcome_text, parse_mode="HTML")


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
    await msg.reply_text("where's yo job at nigga")
    return

  # 3. Standard Custom Chat Triggers
  for keyword, response in TRIGGERS.items():
    if keyword in text_lower:
      await msg.reply_text(response)
      return

  # 4. AFK Screening Trigger
  if "gotti" in text_lower and afk_users:
    await msg.reply_text(
        "he doesn't feel like talking to you right now bitch I'll be taking his"
        " calls"
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

  punishment_msg = "fuck yo mama u dork"

  try:
    await msg.delete()

    until_date = int(time.time() + MUTE_DURATION)
    permissions = ChatPermissions(can_send_messages=False)
    await chat.restrict_member(user.id, permissions, until_date=until_date)

    reason_note = (
        "(Muted for 3 hours: Telegram link detected)"
        if has_telegram_spam
        else "(Muted for 3 hours: Spam detected)"
    )

    await chat.send_message(
        f"{user.mention_html()} {punishment_msg} *{reason_note}*",
        parse_mode="HTML",
    )
  except Exception:
    await msg.reply_text(
        f"{punishment_msg} (Note: Failed to mute user, check bot admin"
        f" permissions.)"
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
  app.add_handler(CommandHandler("afk", toggle_afk))
  app.add_handler(CommandHandler("back", toggle_afk))
  app.add_handler(CommandHandler("dice", dice_command))
  app.add_handler(CommandHandler("slots", slots_command))
  app.add_handler(CommandHandler("stats", stats_command))

  print("Mercedes casino is open, tables are hot, and security is locked down!")
  app.run_polling()


if __name__ == "__main__":
  main()
