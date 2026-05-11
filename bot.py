import os
import logging
import html
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8672987442:AAHvK5dTG42X3Dmpo842AoPo_KlWNeOlonI")
API_KEY = os.getenv("API_KEY", "mrafrix")
BASE_URL = os.getenv("BASE_URL", "https://apis.sage.dpdns.org/api/v1")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def api_get(path: str, params: dict | None = None, timeout: int = 30) -> dict:
    p = dict(params or {})
    p["api_key"] = API_KEY
    qs = "&".join(f"{k}={requests.utils.quote(str(v), safe='')}" for k, v in p.items())
    url = f"{BASE_URL}{path}?{qs}"
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP {e.response.status_code} from API") from None
    except requests.exceptions.RequestException:
        raise RuntimeError("Failed to reach API") from None
    try:
        j = r.json()
    except Exception:
        raise RuntimeError("Invalid API response") from None
    if not j.get("success", False):
        raise RuntimeError(j.get("error") or "API error")
    return j.get("data", {})


def esc(s) -> str:
    return html.escape(str(s) if s is not None else "")


def truncate(s: str, n: int = 60) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🎵 Song / Music", callback_data="menu|music"),
         InlineKeyboardButton("🎬 Video DL", callback_data="menu|video")],
        [InlineKeyboardButton("📥 Social DL", callback_data="menu|social"),
         InlineKeyboardButton("🔎 Search", callback_data="menu|search")],
        [InlineKeyboardButton("🛠 Tools", callback_data="menu|tools"),
         InlineKeyboardButton("🕵️ Stalk", callback_data="menu|stalk")],
        [InlineKeyboardButton("🎲 Fun / Games", callback_data="menu|fun"),
         InlineKeyboardButton("💰 Crypto", callback_data="menu|crypto")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="menu|help")],
    ]
    return InlineKeyboardMarkup(rows)


SUBMENUS = {
    "music": [
        ("🎵 /song <name>", "Search & download MP3"),
        ("🎧 /play <name>", "Same as /song"),
        ("🎼 /lyrics <song>", "Get lyrics"),
        ("☁️ /soundcloud <url>", "SoundCloud info"),
        ("💚 /spotify <url>", "Spotify info"),
    ],
    "video": [
        ("🎬 /video <name>", "Search & download MP4"),
        ("📺 /ytmp4 <url>", "Direct YT video"),
        ("🎵 /ytmp3 <url>", "Direct YT audio"),
    ],
    "social": [
        ("📸 /ig <url>", "Instagram"),
        ("🎵 /tiktok <url>", "TikTok"),
        ("📘 /fb <url>", "Facebook"),
        ("🐦 /twitter <url>", "Twitter / X"),
        ("📌 /pinterest <url>", "Pinterest"),
    ],
    "search": [
        ("🌐 /google <q>", "Web search"),
        ("📷 /image <q>", "Image search"),
        ("📺 /yts <q>", "YouTube search"),
        ("📰 /news <q>", "News"),
        ("🎬 /movie <q>", "Movie info"),
        ("📚 /wiki <q>", "Wikipedia"),
        ("🐙 /ghsearch <q>", "GitHub repos"),
        ("💬 /so <q>", "Stack Overflow"),
        ("📦 /npm <q>", "NPM package"),
    ],
    "tools": [
        ("📷 /qr <text>", "Generate QR"),
        ("🔗 /shorten <url>", "Short URL"),
        ("☁️ /weather <city>", "Weather"),
        ("🌍 /translate <to> <text>", "Translate"),
        ("📡 /ip <ip>", "IP lookup"),
        ("🌐 /dns <domain>", "DNS lookup"),
        ("📄 /whois <domain>", "WHOIS"),
        ("🔒 /ssl <domain>", "SSL check"),
        ("🔐 /password [len]", "Password gen"),
        ("🆔 /uuid", "UUID"),
        ("#️⃣ /hash <text>", "SHA256"),
        ("🏳️ /country <name>", "Country info"),
        ("💱 /currency <amt> <from> <to>", "Currency"),
        ("📍 /myip", "Server IP"),
    ],
    "stalk": [
        ("🐙 /ghuser <username>", "GitHub profile"),
        ("📸 /igstalk <username>", "Instagram profile"),
        ("🎵 /ttstalk <username>", "TikTok profile"),
        ("📺 /ytstalk <channel>", "YouTube channel"),
        ("🐦 /twstalk <username>", "Twitter profile"),
    ],
    "fun": [
        ("😂 /joke", "Random joke"),
        ("💬 /quote", "Quote"),
        ("🧠 /fact", "Useless fact"),
        ("🤣 /meme", "Meme"),
        ("🎯 /trivia", "Trivia"),
        ("🪙 /coinflip", "Flip coin"),
        ("🎲 /dice [sides]", "Roll dice"),
        ("🎱 /8ball <q>", "Magic 8-ball"),
    ],
    "crypto": [
        ("📈 /trending", "Trending coins"),
    ],
}


def submenu_text(key: str) -> str:
    items = SUBMENUS.get(key, [])
    lines = [f"<b>{key.upper()} commands</b>\n"]
    for cmd, desc in items:
        lines.append(f"<code>{esc(cmd)}</code> — {esc(desc)}")
    return "\n".join(lines)


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to menu", callback_data="menu|main")]])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = (
        "🤖 <b>SAGE BOT</b>\n"
        "Powered by SAGE APIs — 275+ endpoints.\n\n"
        "Tap a category below or type /help."
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_menu())
    else:
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_menu())


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start(update, ctx)


async def menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, key = q.data.split("|", 1)
    if key == "main":
        await q.edit_message_text(
            "🤖 <b>SAGE BOT</b>\nChoose a category:",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return
    if key == "help":
        await q.edit_message_text(submenu_text("tools"), parse_mode=ParseMode.HTML, reply_markup=back_kb())
        return
    await q.edit_message_text(submenu_text(key), parse_mode=ParseMode.HTML, reply_markup=back_kb())


def require_args(update: Update, ctx, usage: str) -> str | None:
    if not ctx.args:
        return None
    return " ".join(ctx.args)


async def need(update: Update, usage: str):
    await update.message.reply_text(f"Usage: <code>{esc(usage)}</code>", parse_mode=ParseMode.HTML)


async def song_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _yt_search_select(update, ctx, mode="audio")


async def video_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _yt_search_select(update, ctx, mode="video")


async def _yt_search_select(update: Update, ctx, mode: str):
    q = " ".join(ctx.args)
    if not q:
        await need(update, ("/song" if mode == "audio" else "/video") + " <name>")
        return
    msg = await update.message.reply_text("🔍 Searching YouTube…")
    try:
        data = api_get("/search/youtube", {"query": q})
        results = data.get("results", [])[:6]
    except Exception as e:
        await msg.edit_text(f"❌ {esc(e)}")
        return
    if not results:
        await msg.edit_text("😕 No results.")
        return
    rows = []
    for i, r in enumerate(results):
        label = f"{i+1}. {truncate(r.get('title',''), 45)} ({r.get('duration','')})"
        rows.append([InlineKeyboardButton(label, callback_data=f"yt|{mode}|{r['videoId']}")])
    rows.append([InlineKeyboardButton("✖️ Cancel", callback_data="cancel|")])
    icon = "🎵" if mode == "audio" else "🎬"
    await msg.edit_text(
        f"{icon} <b>Results for:</b> <code>{esc(q)}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def yt_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, mode, vid = q.data.split("|", 2)
    await q.edit_message_text("⏳ Fetching download…")
    try:
        ep = "/downloads/ytmp3" if mode == "audio" else "/downloads/ytmp4"
        data = api_get(ep, {"url": f"https://youtube.com/watch?v={vid}"})
        dl = data.get("url") or data.get("download")
        if not dl:
            raise RuntimeError("No URL returned")
        title = data.get("title", "Unknown")
        if mode == "audio":
            await q.edit_message_text("📤 Sending audio…")
            await ctx.bot.send_audio(
                chat_id=q.message.chat_id,
                audio=dl,
                title=title,
                performer=data.get("uploader", ""),
                duration=data.get("duration"),
            )
        else:
            await q.edit_message_text("📤 Sending video…")
            await ctx.bot.send_video(
                chat_id=q.message.chat_id,
                video=dl,
                caption=f"🎬 {title}",
                supports_streaming=True,
            )
        await q.delete_message()
    except Exception as e:
        logger.exception("yt cb")
        await q.edit_message_text(f"❌ Download failed: {esc(e)}")


async def cancel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Cancelled")
    try:
        await update.callback_query.delete_message()
    except Exception:
        pass


async def ytmp3_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ytmp3 <youtube_url>"); return
    url = ctx.args[0]
    m = await update.message.reply_text("⏳ Fetching audio…")
    try:
        d = api_get("/downloads/ytmp3", {"url": url})
        dl = d.get("url") or d.get("download")
        await ctx.bot.send_audio(update.effective_chat.id, audio=dl, title=d.get("title"), performer=d.get("uploader"), duration=d.get("duration"))
        await m.delete()
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def ytmp4_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ytmp4 <youtube_url>"); return
    url = ctx.args[0]
    m = await update.message.reply_text("⏳ Fetching video…")
    try:
        d = api_get("/downloads/ytmp4", {"url": url})
        dl = d.get("url") or d.get("download")
        await ctx.bot.send_video(update.effective_chat.id, video=dl, caption=f"🎬 {d.get('title','')}", supports_streaming=True)
        await m.delete()
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def ig_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ig <instagram_url>"); return
    m = await update.message.reply_text("⏳ Fetching…")
    try:
        d = api_get("/downloads/instagram", {"url": ctx.args[0]})
        txt = f"📸 <b>Instagram</b>\n<code>{esc(d.get('source',''))}</code>\nShortcode: <code>{esc(d.get('shortcode',''))}</code>"
        await m.edit_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def tiktok_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/tiktok <url>"); return
    m = await update.message.reply_text("⏳ Fetching…")
    try:
        d = api_get("/downloads/tiktok", {"url": ctx.args[0]})
        await m.edit_text(f"🎵 TikTok:\n<pre>{esc(str(d)[:1500])}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def fb_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/fb <facebook_url>"); return
    m = await update.message.reply_text("⏳ Fetching…")
    try:
        d = api_get("/downloads/facebook", {"url": ctx.args[0]})
        await m.edit_text(f"📘 <b>{esc(d.get('title',''))}</b>\n\n{esc(d.get('description',''))}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def twitter_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/twitter <url>"); return
    m = await update.message.reply_text("⏳ Fetching…")
    try:
        d = api_get("/downloads/twitter", {"url": ctx.args[0]})
        a = d.get("author") or {}
        txt = (
            f"🐦 <b>{esc(a.get('name',''))}</b> @{esc(a.get('screen_name',''))}\n\n"
            f"{esc(d.get('text',''))}\n\n"
            f"❤️ {d.get('likes',0)} | 🔁 {d.get('retweets',0)} | 💬 {d.get('replies',0)}"
        )
        media = d.get("media") or []
        photos = [x for x in media if x.get("type", "photo") == "photo"]
        if photos:
            urls = []
            for p in photos[:4]:
                u = p.get("media_url_https") or p.get("media_url") or p.get("url")
                if u: urls.append(u)
            if urls:
                await m.delete()
                if len(urls) == 1:
                    await ctx.bot.send_photo(update.effective_chat.id, urls[0], caption=txt, parse_mode=ParseMode.HTML)
                else:
                    grp = [InputMediaPhoto(u, caption=txt if i == 0 else None, parse_mode=ParseMode.HTML if i == 0 else None) for i, u in enumerate(urls)]
                    await ctx.bot.send_media_group(update.effective_chat.id, grp)
                return
        await m.edit_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def pinterest_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/pinterest <url>"); return
    m = await update.message.reply_text("⏳ Fetching…")
    try:
        d = api_get("/downloads/pinterest", {"url": ctx.args[0]})
        await m.edit_text(f"📌 Pinterest:\n<pre>{esc(str(d)[:1500])}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def spotify_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/spotify <url>"); return
    m = await update.message.reply_text("⏳ Fetching…")
    try:
        d = api_get("/downloads/spotify", {"url": ctx.args[0]})
        meta = d.get("metadata", {})
        txt = f"💚 <b>{esc(meta.get('title',''))}</b>\nProvider: {esc(meta.get('provider_name',''))}\n<a href=\"{esc(meta.get('iframe_url',''))}\">Open</a>"
        thumb = meta.get("thumbnail_url")
        if thumb:
            await m.delete()
            await ctx.bot.send_photo(update.effective_chat.id, thumb, caption=txt, parse_mode=ParseMode.HTML)
        else:
            await m.edit_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def soundcloud_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/soundcloud <url>"); return
    m = await update.message.reply_text("⏳ Fetching…")
    try:
        d = api_get("/downloads/soundcloud", {"url": ctx.args[0]})
        txt = f"☁️ <b>{esc(d.get('title',''))}</b>\nby {esc(d.get('author',''))}\n<a href=\"{esc(d.get('author_url',''))}\">Artist</a>"
        thumb = d.get("thumbnail")
        if thumb:
            await m.delete()
            await ctx.bot.send_photo(update.effective_chat.id, thumb, caption=txt, parse_mode=ParseMode.HTML)
        else:
            await m.edit_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def google_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/google <query>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("🔍 Searching…")
    try:
        d = api_get("/search/google", {"query": q})
        results = d.get("results", [])[:8]
        if not results:
            await m.edit_text("😕 No results."); return
        lines = [f"🌐 <b>Google:</b> <code>{esc(q)}</code>\n"]
        for r in results:
            lines.append(f"• <a href=\"{esc(r.get('url',''))}\">{esc(truncate(r.get('title',''),80))}</a>\n  <i>{esc(truncate(r.get('snippet',''),120))}</i>")
        await m.edit_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def image_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/image <query>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("🔍 Searching images…")
    try:
        d = api_get("/search/images", {"query": q})
        results = [r.get("image") for r in d.get("results", []) if r.get("image")][:5]
        if not results:
            await m.edit_text("😕 No images."); return
        await m.delete()
        if len(results) == 1:
            await ctx.bot.send_photo(update.effective_chat.id, results[0], caption=f"📷 {esc(q)}", parse_mode=ParseMode.HTML)
        else:
            grp = [InputMediaPhoto(u, caption=f"📷 {esc(q)}" if i == 0 else None, parse_mode=ParseMode.HTML if i == 0 else None) for i, u in enumerate(results)]
            await ctx.bot.send_media_group(update.effective_chat.id, grp)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def yts_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/yts <query>"); return
    await _yt_search_select(update, ctx, mode="audio")


async def news_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/news <query>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("🔍 Fetching news…")
    try:
        d = api_get("/search/news", {"query": q})
        results = d.get("results", [])[:6]
        if not results:
            await m.edit_text("😕 No news."); return
        lines = [f"📰 <b>News for:</b> <code>{esc(q)}</code>\n"]
        for r in results:
            lines.append(f"• <a href=\"{esc(r.get('url',''))}\">{esc(truncate(r.get('title',''),80))}</a>\n  <i>{esc(r.get('source',''))}</i>")
        await m.edit_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def movie_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/movie <title>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("🔍 Looking up movie…")
    try:
        d = api_get("/search/movie", {"query": q})
        r = d.get("results", [d])[0] if isinstance(d.get("results"), list) else d
        title = r.get("title") or r.get("Title") or d.get("title")
        plot = r.get("plot") or r.get("Plot") or r.get("overview") or ""
        year = r.get("year") or r.get("Year") or r.get("release_date", "")
        poster = r.get("poster") or r.get("Poster") or r.get("image")
        rating = r.get("imdbRating") or r.get("rating") or r.get("vote_average")
        txt = f"🎬 <b>{esc(title)}</b> ({esc(year)})\n⭐ {esc(rating)}\n\n{esc(truncate(plot, 700))}"
        if poster and poster.startswith("http"):
            await m.delete()
            await ctx.bot.send_photo(update.effective_chat.id, poster, caption=txt, parse_mode=ParseMode.HTML)
        else:
            await m.edit_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def wiki_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/wiki <topic>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("📚 Searching Wikipedia…")
    try:
        d = api_get("/search/wikipedia", {"query": q})
        if isinstance(d, dict) and d.get("results"):
            r = d["results"][0]
        else:
            r = d
        title = r.get("title", q)
        extract = r.get("extract") or r.get("snippet") or r.get("description") or ""
        url = r.get("url") or r.get("link") or ""
        await m.edit_text(
            f"📚 <b>{esc(title)}</b>\n\n{esc(truncate(extract, 1500))}\n\n<a href=\"{esc(url)}\">Read more</a>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        )
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def ghsearch_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ghsearch <query>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("🔍 Searching GitHub…")
    try:
        d = api_get("/search/github", {"query": q})
        results = d.get("results", []) if isinstance(d, dict) else []
        if not results and isinstance(d, dict) and d.get("items"):
            results = d["items"]
        lines = [f"🐙 <b>GitHub:</b> <code>{esc(q)}</code>\n"]
        for r in results[:8]:
            name = r.get("full_name") or r.get("name") or ""
            url = r.get("html_url") or r.get("url") or ""
            desc = r.get("description") or ""
            stars = r.get("stargazers_count") or r.get("stars") or 0
            lines.append(f"• <a href=\"{esc(url)}\">{esc(name)}</a> ⭐ {stars}\n  <i>{esc(truncate(desc,100))}</i>")
        await m.edit_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def so_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/so <query>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("🔍 Stack Overflow…")
    try:
        d = api_get("/search/stackoverflow", {"query": q})
        results = d.get("results", []) if isinstance(d, dict) else []
        if not results and isinstance(d, dict) and d.get("items"):
            results = d["items"]
        lines = [f"💬 <b>Stack Overflow:</b> <code>{esc(q)}</code>\n"]
        for r in results[:8]:
            title = r.get("title", "")
            url = r.get("link") or r.get("url") or ""
            lines.append(f"• <a href=\"{esc(url)}\">{esc(truncate(title,100))}</a>")
        await m.edit_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def npm_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/npm <package>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("📦 Searching NPM…")
    try:
        d = api_get("/search/npm", {"query": q})
        results = d.get("results", []) if isinstance(d, dict) else []
        if not results and isinstance(d, dict) and d.get("objects"):
            results = [o.get("package", {}) for o in d["objects"]]
        lines = [f"📦 <b>NPM:</b> <code>{esc(q)}</code>\n"]
        for r in results[:8]:
            name = r.get("name", "")
            ver = r.get("version", "")
            desc = r.get("description", "")
            url = r.get("links", {}).get("npm") if isinstance(r.get("links"), dict) else r.get("url", "")
            lines.append(f"• <b>{esc(name)}</b> <code>{esc(ver)}</code>\n  <i>{esc(truncate(desc,120))}</i>\n  {esc(url)}")
        await m.edit_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def lyrics_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/lyrics <song>"); return
    q = " ".join(ctx.args)
    m = await update.message.reply_text("🎼 Fetching lyrics…")
    try:
        d = api_get("/search/lyrics", {"query": q})
        title = d.get("song") or d.get("title") or q
        artist = d.get("artist", "")
        lyrics = d.get("lyrics", "")
        cover = d.get("cover")
        head = f"🎼 <b>{esc(title)}</b> — {esc(artist)}\n\n"
        chunk_size = 3800
        chunks = [lyrics[i:i + chunk_size] for i in range(0, len(lyrics), chunk_size)] or [""]
        if cover:
            await m.delete()
            await ctx.bot.send_photo(update.effective_chat.id, cover, caption=head + esc(chunks[0]), parse_mode=ParseMode.HTML)
            for c in chunks[1:]:
                await ctx.bot.send_message(update.effective_chat.id, esc(c), parse_mode=ParseMode.HTML)
        else:
            await m.edit_text(head + esc(chunks[0]), parse_mode=ParseMode.HTML)
            for c in chunks[1:]:
                await update.message.reply_text(esc(c), parse_mode=ParseMode.HTML)
    except Exception as e:
        await m.edit_text(f"❌ {esc(e)}")


async def qr_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/qr <text>"); return
    text = " ".join(ctx.args)
    try:
        d = api_get("/tools/qr", {"text": text})
        await update.message.reply_photo(d.get("image") or d.get("url"), caption=f"📷 QR for: <code>{esc(text)}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def shorten_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/shorten <url>"); return
    try:
        d = api_get("/tools/shorten", {"url": ctx.args[0]})
        await update.message.reply_text(f"🔗 <b>Short URL:</b>\n<code>{esc(d.get('short',''))}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def weather_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/weather <city>"); return
    loc = " ".join(ctx.args)
    try:
        d = api_get("/tools/weather", {"location": loc})
        cur = d.get("current", {})
        txt = (
            f"☁️ <b>Weather:</b> {esc(d.get('location',''))}\n"
            f"🌡 Temp: <b>{cur.get('temperature','?')}°C</b>\n"
            f"💨 Wind: {cur.get('windspeed','?')} km/h\n"
            f"☀️ Day: {'Yes' if cur.get('is_day') else 'No'}\n"
            f"🕒 {esc(cur.get('time',''))} ({esc(d.get('timezone',''))})"
        )
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def translate_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await need(update, "/translate <to_lang> <text>"); return
    to_lang = ctx.args[0]
    text = " ".join(ctx.args[1:])
    try:
        d = api_get("/tools/translate", {"text": text, "to": to_lang})
        await update.message.reply_text(f"🌍 <b>{esc(to_lang)}:</b>\n{esc(d.get('translated',''))}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def ip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ip <ip-address>"); return
    try:
        d = api_get("/tools/iplookup", {"ip": ctx.args[0]})
        txt = (
            f"📡 <b>{esc(d.get('query', ctx.args[0]))}</b>\n"
            f"🌍 {esc(d.get('country',''))} ({esc(d.get('countryCode',''))})\n"
            f"🏙 {esc(d.get('city',''))}, {esc(d.get('regionName',''))}\n"
            f"🕒 {esc(d.get('timezone',''))}\n"
            f"📡 ISP: {esc(d.get('isp',''))}\n"
            f"🏢 Org: {esc(d.get('org',''))}\n"
            f"📍 {d.get('lat','')}, {d.get('lon','')}"
        )
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def dns_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/dns <domain>"); return
    try:
        d = api_get("/tools/dns", {"domain": ctx.args[0]})
        ans = d.get("answers", [])
        lines = [f"🌐 <b>DNS {esc(d.get('type','A'))}:</b> {esc(d.get('domain',''))}\n"]
        for a in ans[:15]:
            lines.append(f"• <code>{esc(a.get('data',''))}</code> (TTL {a.get('TTL','?')})")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def whois_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/whois <domain>"); return
    try:
        d = api_get("/tools/whois", {"domain": ctx.args[0]})
        events = d.get("events", []) or []
        ev_lines = "\n".join(f"• {esc(e.get('eventAction',''))}: <code>{esc(e.get('eventDate',''))}</code>" for e in events[:6])
        ns = d.get("nameservers") or []
        ns_lines = ", ".join(esc(n.get('ldhName','') if isinstance(n, dict) else n) for n in ns[:6])
        txt = (
            f"📄 <b>WHOIS:</b> {esc(d.get('ldhName', d.get('domain','')))}\n"
            f"🆔 Handle: <code>{esc(d.get('handle',''))}</code>\n"
            f"🌐 NS: {ns_lines or '—'}\n\n{ev_lines}"
        )
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def ssl_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ssl <domain>"); return
    try:
        d = api_get("/tools/ssl", {"domain": ctx.args[0]})
        ok = "✅ Secure" if d.get("secure") else "❌ Not secure"
        server = d.get("headers", {}).get("server", "")
        await update.message.reply_text(
            f"🔒 <b>SSL {esc(d.get('domain',''))}</b>\n{ok}\nStatus: <code>{d.get('status','?')}</code>\nServer: <code>{esc(server)}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def password_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        length = int(ctx.args[0]) if ctx.args else 16
    except Exception:
        length = 16
    try:
        d = api_get("/misc/password", {"length": length})
        await update.message.reply_text(
            f"🔐 <code>{esc(d.get('password',''))}</code>\nLength: {d.get('length')} | Strength: {esc(d.get('strength',''))}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def uuid_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/misc/uuid")
        await update.message.reply_text(f"🆔 <code>{esc(d.get('uuid',''))}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def hash_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/hash <text>"); return
    text = " ".join(ctx.args)
    try:
        d = api_get("/misc/hash", {"text": text, "algo": "sha256"})
        await update.message.reply_text(
            f"#️⃣ <b>{esc(d.get('algorithm','SHA256'))}</b>\n<code>{esc(d.get('hash',''))}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def country_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/country <name>"); return
    name = " ".join(ctx.args)
    try:
        d = api_get("/misc/country", {"name": name})
        c = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})
        names = c.get("name", {})
        flag = c.get("flag", "")
        common = names.get("common", "") if isinstance(names, dict) else ""
        official = names.get("official", "") if isinstance(names, dict) else ""
        cap = ", ".join(c.get("capital", []) or [])
        region = c.get("region", "")
        sub = c.get("subregion", "")
        pop = c.get("population", "")
        currencies = ", ".join((c.get("currencies") or {}).keys()) if isinstance(c.get("currencies"), dict) else ""
        langs = ", ".join((c.get("languages") or {}).values()) if isinstance(c.get("languages"), dict) else ""
        txt = (
            f"🏳️ <b>{esc(flag)} {esc(common)}</b>\n<i>{esc(official)}</i>\n\n"
            f"🏛 Capital: {esc(cap)}\n🌍 Region: {esc(region)} ({esc(sub)})\n"
            f"👥 Population: {pop}\n💱 Currency: {esc(currencies)}\n🗣 Languages: {esc(langs)}"
        )
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def currency_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 3:
        await need(update, "/currency <amount> <from> <to>"); return
    try:
        amount = float(ctx.args[0])
        d = api_get("/converter/currency", {"amount": amount, "from": ctx.args[1], "to": ctx.args[2]})
        rate = d.get("rate")
        result = d.get("result") or (amount * rate if rate else None)
        await update.message.reply_text(
            f"💱 <b>{amount} {esc(d.get('from',''))}</b> ≈ <b>{result} {esc(d.get('to',''))}</b>\nRate: {rate}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def myip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/misc/ip")
        await update.message.reply_text(
            f"📍 IP: <code>{esc(d.get('ip',''))}</code>\n🌍 {esc(d.get('country',''))} — {esc(d.get('city',''))}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def ghuser_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ghuser <username>"); return
    try:
        d = api_get("/stalk/github", {"username": ctx.args[0]})
        txt = (
            f"🐙 <b>{esc(d.get('name') or d.get('login',''))}</b> (@{esc(d.get('login',''))})\n"
            f"{esc(d.get('bio',''))}\n\n"
            f"📍 {esc(d.get('location',''))}\n🏢 {esc(d.get('company',''))}\n"
            f"👥 Followers: <b>{d.get('followers','?')}</b> | Following: {d.get('following','?')}\n"
            f"📦 Repos: <b>{d.get('public_repos','?')}</b>\n"
            f"<a href=\"{esc(d.get('html_url',''))}\">Profile</a>"
        )
        avatar = d.get("avatar_url")
        if avatar:
            await update.message.reply_photo(avatar, caption=txt, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def igstalk_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/igstalk <username>"); return
    try:
        d = api_get("/stalk/instagram", {"username": ctx.args[0]})
        txt = (
            f"📸 <b>{esc(d.get('fullName',''))}</b> (@{esc(d.get('username',''))}) {'✅' if d.get('isVerified') else ''}\n"
            f"{esc(d.get('biography',''))}\n\n"
            f"👥 Followers: <b>{d.get('followers','?')}</b>\n"
            f"➡️ Following: {d.get('following','?')}\n"
            f"📷 Posts: {d.get('posts','?')}\n"
            f"🔗 {esc(d.get('externalUrl',''))}"
        )
        pic = d.get("profilePicUrl") or d.get("profile_pic_url") or d.get("avatar")
        if pic:
            await update.message.reply_photo(pic, caption=txt, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def ttstalk_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ttstalk <username>"); return
    try:
        d = api_get("/stalk/tiktok", {"username": ctx.args[0]})
        u = d.get("user", {}) or {}
        stats = d.get("stats", {}) or {}
        txt = (
            f"🎵 <b>{esc(u.get('nickname',''))}</b> (@{esc(u.get('uniqueId',''))}) {'✅' if u.get('verified') else ''}\n"
            f"{esc(u.get('signature',''))}\n\n"
            f"👥 Followers: <b>{stats.get('followerCount','?')}</b>\n"
            f"❤️ Hearts: {stats.get('heartCount','?')}\n"
            f"🎬 Videos: {stats.get('videoCount','?')}"
        )
        pic = u.get("avatarLarger") or u.get("avatarMedium")
        if pic:
            await update.message.reply_photo(pic, caption=txt, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def ytstalk_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/ytstalk <channel>"); return
    try:
        d = api_get("/stalk/youtube", {"channel": ctx.args[0]})
        await update.message.reply_text(f"📺 <pre>{esc(str(d)[:2500])}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def twstalk_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/twstalk <username>"); return
    try:
        d = api_get("/stalk/twitter", {"username": ctx.args[0]})
        await update.message.reply_text(f"🐦 <pre>{esc(str(d)[:2500])}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def joke_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/fun/joke")
        if d.get("type") == "twopart":
            txt = f"😂 {esc(d.get('setup',''))}\n\n<tg-spoiler>{esc(d.get('delivery',''))}</tg-spoiler>"
        else:
            txt = f"😂 {esc(d.get('joke',''))}"
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def quote_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/fun/quote")
        await update.message.reply_text(f"💬 <i>{esc(d.get('content',''))}</i>\n— <b>{esc(d.get('author',''))}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def fact_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/fun/fact")
        await update.message.reply_text(f"🧠 {esc(d.get('text',''))}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def meme_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/fun/meme")
        cap = f"🤣 <b>{esc(d.get('title',''))}</b>\nr/{esc(d.get('subreddit',''))} • 👍 {d.get('ups',0)}"
        await update.message.reply_photo(d.get("url"), caption=cap, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def trivia_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/games/trivia")
        opts = d.get("options") or []
        rows = [[InlineKeyboardButton(o, callback_data=f"trv|{'1' if o == d.get('answer') else '0'}")] for o in opts]
        txt = f"🎯 <b>{esc(d.get('category',''))}</b> ({esc(d.get('difficulty',''))})\n\n{esc(d.get('question',''))}"
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def trivia_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, correct = q.data.split("|", 1)
    await q.answer("✅ Correct!" if correct == "1" else "❌ Wrong", show_alert=True)


async def coinflip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/games/coinflip")
        await update.message.reply_text(f"🪙 <b>{esc(d.get('result',''))}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def dice_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        sides = int(ctx.args[0]) if ctx.args else 6
    except Exception:
        sides = 6
    try:
        d = api_get("/games/dice", {"sides": sides})
        await update.message.reply_text(f"🎲 Rolled <b>{d.get('sum','?')}</b> on d{sides}\n{d.get('rolls',[])}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def eightball_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await need(update, "/8ball <question>"); return
    q = " ".join(ctx.args)
    try:
        d = api_get("/games/8ball", {"question": q})
        await update.message.reply_text(f"🎱 Q: <i>{esc(q)}</i>\nA: <b>{esc(d.get('answer',''))}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def trending_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = api_get("/crypto/trending")
        coins = d.get("coins", [])[:10]
        lines = ["📈 <b>Trending Crypto</b>\n"]
        for c in coins:
            it = c.get("item", c)
            lines.append(f"• <b>{esc(it.get('name',''))}</b> ({esc(it.get('symbol',''))}) — rank #{it.get('market_cap_rank','?')}")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {esc(e)}")


async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command. Try /help.")


async def on_error(update, ctx):
    logger.error("Update error", exc_info=ctx.error)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler(["start", "help", "menu"], start))

    app.add_handler(CommandHandler("song", song_handler))
    app.add_handler(CommandHandler("play", song_handler))
    app.add_handler(CommandHandler("video", video_handler))
    app.add_handler(CommandHandler("ytmp3", ytmp3_cmd))
    app.add_handler(CommandHandler("ytmp4", ytmp4_cmd))
    app.add_handler(CommandHandler("yts", yts_cmd))

    app.add_handler(CommandHandler("ig", ig_cmd))
    app.add_handler(CommandHandler("instagram", ig_cmd))
    app.add_handler(CommandHandler("tiktok", tiktok_cmd))
    app.add_handler(CommandHandler(["fb", "facebook"], fb_cmd))
    app.add_handler(CommandHandler(["twitter", "x"], twitter_cmd))
    app.add_handler(CommandHandler("pinterest", pinterest_cmd))
    app.add_handler(CommandHandler("spotify", spotify_cmd))
    app.add_handler(CommandHandler("soundcloud", soundcloud_cmd))

    app.add_handler(CommandHandler("google", google_cmd))
    app.add_handler(CommandHandler(["image", "images", "img"], image_cmd))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("movie", movie_cmd))
    app.add_handler(CommandHandler("wiki", wiki_cmd))
    app.add_handler(CommandHandler("ghsearch", ghsearch_cmd))
    app.add_handler(CommandHandler("so", so_cmd))
    app.add_handler(CommandHandler("npm", npm_cmd))
    app.add_handler(CommandHandler("lyrics", lyrics_cmd))

    app.add_handler(CommandHandler("qr", qr_cmd))
    app.add_handler(CommandHandler("shorten", shorten_cmd))
    app.add_handler(CommandHandler("weather", weather_cmd))
    app.add_handler(CommandHandler("translate", translate_cmd))
    app.add_handler(CommandHandler("ip", ip_cmd))
    app.add_handler(CommandHandler("dns", dns_cmd))
    app.add_handler(CommandHandler("whois", whois_cmd))
    app.add_handler(CommandHandler("ssl", ssl_cmd))
    app.add_handler(CommandHandler("password", password_cmd))
    app.add_handler(CommandHandler("uuid", uuid_cmd))
    app.add_handler(CommandHandler("hash", hash_cmd))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("currency", currency_cmd))
    app.add_handler(CommandHandler("myip", myip_cmd))

    app.add_handler(CommandHandler("ghuser", ghuser_cmd))
    app.add_handler(CommandHandler("igstalk", igstalk_cmd))
    app.add_handler(CommandHandler("ttstalk", ttstalk_cmd))
    app.add_handler(CommandHandler("ytstalk", ytstalk_cmd))
    app.add_handler(CommandHandler("twstalk", twstalk_cmd))

    app.add_handler(CommandHandler("joke", joke_cmd))
    app.add_handler(CommandHandler("quote", quote_cmd))
    app.add_handler(CommandHandler("fact", fact_cmd))
    app.add_handler(CommandHandler("meme", meme_cmd))
    app.add_handler(CommandHandler("trivia", trivia_cmd))
    app.add_handler(CommandHandler("coinflip", coinflip_cmd))
    app.add_handler(CommandHandler("dice", dice_cmd))
    app.add_handler(CommandHandler("8ball", eightball_cmd))
    app.add_handler(CommandHandler("trending", trending_cmd))

    app.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^menu\|"))
    app.add_handler(CallbackQueryHandler(yt_cb, pattern=r"^yt\|"))
    app.add_handler(CallbackQueryHandler(trivia_cb, pattern=r"^trv\|"))
    app.add_handler(CallbackQueryHandler(cancel_cb, pattern=r"^cancel\|"))

    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_error_handler(on_error)

    logger.info("SAGE BOT running…")

    port = int(os.getenv("PORT", 8080))

    class _Health(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *a):
            pass

    server = HTTPServer(("0.0.0.0", port), _Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Health server on port %d", port)

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
