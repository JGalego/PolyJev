# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=10", "matplotlib>=3.8", "piper-tts>=1.3"]
# ///
"""Generate the demo app's examples: one or more per option of every Jev. `uv run demo/examples/make.py` (needs ffmpeg).

Images are drawn with Pillow and matplotlib, speech is synthesized offline with Piper (voices are downloaded once into
~/.cache/polyjev/voices), and each video is four 2-second scenes, because a Jev looks at one frame from the middle of each
quarter of a clip. Writes demo/examples/<jev>/* and demo/examples/examples.json, which the demo app reads.
"""

import io
import json
import math
import re
import subprocess
import sys
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont
from piper import PiperVoice

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
VOICES = Path.home() / ".cache" / "polyjev" / "voices"
W, H = 640, 360
Img = Image.Image
Draw = ImageDraw.ImageDraw

# ---------------------------------------------------------------------------------------------------------------- drawing

_fonts: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if (size, bold) not in _fonts:
        path = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold" if bold else "normal"))
        _fonts[size, bold] = ImageFont.truetype(path, size)
    return _fonts[size, bold]


def canvas(bg: str = "#f3f3f3", w: int = W, h: int = H) -> tuple[Img, Draw]:
    img = Image.new("RGB", (w, h), bg)
    return img, ImageDraw.Draw(img)


def window(title: str, w: int = W, h: int = H, bar: str = "#2b579a") -> tuple[Img, Draw]:
    """An app window like the bundled samples: a blue title bar over a light body."""
    img, d = canvas(w=w, h=h)
    d.rectangle((0, 0, w, 40), fill=bar)
    d.text((16, 10), title, font=font(18, True), fill="white")
    return img, d


def write(d: Draw, xy: tuple[int, int], s: str, size: int = 22, fill: str = "#222", bold: bool = False) -> None:
    d.multiline_text(xy, s, font=font(size, bold), fill=fill, spacing=8)


def button(d: Draw, box: tuple[int, int, int, int], label: str, primary: bool = False) -> None:
    d.rounded_rectangle(box, 6, fill="#2b579a" if primary else "white", outline="#888")
    x0, y0, x1, y1 = box
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), label, font=font(18, primary), fill="white" if primary else "#222", anchor="mm")


def progress(d: Draw, pct: int, y: int = 220, color: str = "#2ea44f") -> None:
    d.rectangle((60, y, 580, y + 30), fill="white", outline="#888", width=2)
    d.rectangle((62, y + 2, 62 + int(516 * pct / 100), y + 28), fill=color)


def figure(draw: Callable[[plt.Axes], None], w: int = W, h: int = H) -> Img:
    fig, ax = plt.subplots(figsize=(w / 100, h / 100), dpi=100)
    draw(ax)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return Image.open(buf).convert("RGB")


# ------------------------------------------------------------------------------------------------------------------ media

_voices: dict[str, PiperVoice] = {}
FEMALE, MALE = "en_US-lessac-medium", "en_US-ryan-medium"


def speech(text: str, voice: str, out: Path) -> Path:
    """Synthesize `text` to a 16 kHz mono WAV, the format the bundled samples use."""
    if voice not in _voices:
        if not (VOICES / f"{voice}.onnx").exists():
            VOICES.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "piper.download_voices", "--download-dir", str(VOICES), voice], check=True)
        _voices[voice] = PiperVoice.load(str(VOICES / f"{voice}.onnx"))
    raw = out.with_suffix(".raw.wav")
    with wave.open(str(raw), "wb") as w:
        _voices[voice].synthesize_wav(text, w)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ac", "1", "-ar", "16000", "-bitexact", str(out)], check=True)
    raw.unlink()
    return out


def duration(path: Path) -> float:
    probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    return float(subprocess.run(probe, capture_output=True, check=True, text=True).stdout)


def clip(scenes: list[Img], out: Path, voiceover: Path | None = None) -> Path:
    """Four equal scenes (8 s, or longer to fit the voice-over), 4 fps H.264 with an optional AAC soundtrack.

    The length is a whole number of seconds, so each scene is a whole number of frames and the video and the padded
    soundtrack end together: a Jev spaces its frames by the container's duration, and a mismatch shifts them off the scenes.
    """
    assert len(scenes) == 4, "a Jev samples one frame from the middle of each quarter"
    seconds = float(math.ceil(max(8.0, duration(voiceover) + 0.8))) if voiceover else 8.0
    with tempfile.TemporaryDirectory() as tmp:
        for i, s in enumerate(scenes):
            s.save(f"{tmp}/s{i}.png")
        # One exact-length segment per scene, joined, so every quarter of the clip shows its own scene.
        args = ["ffmpeg", "-v", "error", "-y"]
        for i in range(4):
            args += ["-loop", "1", "-framerate", "4", "-t", f"{seconds / 4}", "-i", f"{tmp}/s{i}.png"]
        video = "".join(f"[{i}:v]" for i in range(4)) + "concat=n=4:v=1:a=0,format=yuv420p[v]"
        if voiceover:
            args += ["-i", str(voiceover), "-filter_complex", f"{video};[4:a]apad[a]", "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-ar", "16000", "-ac", "1"]
        else:
            args += ["-filter_complex", video, "-map", "[v]"]
        args += ["-t", f"{seconds}", "-c:v", "libx264", "-map_metadata", "-1", str(out)]
        subprocess.run(args, check=True)
    return out


# --------------------------------------------------------------------------------------------------------------- examples

Example = dict[str, str]
EXAMPLES: dict[str, list[Example]] = {}


def add(jev: str, label: str, expect: str, **inputs: str | Path) -> None:
    ex: Example = {"label": label, "expect": expect}
    for k, v in inputs.items():
        ex[k] = v.relative_to(HERE).as_posix() if isinstance(v, Path) else v
    EXAMPLES.setdefault(jev, []).append(ex)


def out(jev: str, name: str) -> Path:
    (HERE / jev).mkdir(exist_ok=True)
    return HERE / jev / name


def png(img: Img, jev: str, name: str) -> Path:
    path = out(jev, name)
    img.save(path, optimize=True)
    return path


def text_emails() -> None:
    emails = [
        ("Legitimate: meeting notes", "legitimate",
         "From: Priya Shah <priya.shah@northwind.com>\nSubject: Notes from Thursday's planning meeting\n\nHi all,\n\n"
         "Thanks for joining on Thursday. Action items:\n- Marco: draft the Q4 hiring plan by the 14th\n- Lena: book the room for the offsite\n\n"
         "The slides are in the team folder. Shout if I missed anything.\n\nPriya"),
        ("Legitimate: a colleague asks for a review", "legitimate",
         "From: Lena Weber <lena.weber@northwind.com>\nSubject: Could you look at my pull request?\n\nHi Jo,\n\n"
         "I've opened the PR for the new export screen. It's not urgent, but it would be great to have your review before Friday's release.\n"
         "I left a couple of questions in the comments on the date formatting.\n\nThanks!\nLena"),
        ("Spam: miracle discount", "spam",
         "From: Mega Deals <deals@best-offers-4u.biz>\nSubject: 🔥 90% OFF luxury watches, TODAY ONLY!!!\n\n"
         "Dear Customer,\n\nYou have been SELECTED for our exclusive VIP sale. Genuine designer watches from just $19.99!\n"
         "Free shipping worldwide. Limited stock, act NOW!\n\nTo stop receiving these emails reply REMOVE."),
        ("Spam: newsletter you never signed up for", "spam",
         "From: Crypto Insider <news@moonshot-signals.io>\nSubject: This coin will 100x before Friday\n\n"
         "Our analysts have found the next big thing. Early members already made $12,000 in one week.\n"
         "Join 50,000 traders getting our daily picks. Not financial advice.\n\nUnsubscribe | Update preferences"),
        ("Phishing: fake parcel fee", "phishing",
         "From: DHL Express <noreply@dhl-parcel-release.info>\nSubject: Your parcel is on hold: customs fee unpaid\n\n"
         "We tried to deliver your parcel today but a customs fee of €1.99 is due.\n"
         "Pay within 24 hours or it will be returned to the sender: http://dhl-parcel-release.info/pay\n\nDHL Customer Service"),
        ("Phishing: fake account lock", "phishing",
         "From: PayPal Security <service@paypa1-account-review.com>\nSubject: Your account has been limited\n\n"
         "We noticed unusual activity and have temporarily limited your account.\n"
         "To restore access, log in and confirm your card details within 48 hours: http://paypa1-account-review.com/login\n\nPayPal Security Team"),
    ]
    for label, expect, email in emails:
        add("text", label, expect, text=email)


def image_charts() -> None:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]

    def bar(ax: plt.Axes) -> None:
        ax.bar(["North", "South", "East", "West"], [42, 31, 55, 27], color="#4f79bc")
        ax.set_title("Units sold by region")

    def line(ax: plt.Axes) -> None:
        ax.plot(months, [120, 135, 128, 160, 172, 190], marker="o", color="#d9534f")
        ax.set_title("Monthly active users (thousands)")

    def pie(ax: plt.Axes) -> None:
        ax.pie([45, 30, 15, 10], labels=["Rent", "Salaries", "Marketing", "Other"], autopct="%1.0f%%")
        ax.set_title("Where the budget goes")

    def scatter(ax: plt.Axes) -> None:
        xs = [1.2, 2.3, 2.9, 3.5, 4.1, 4.8, 5.5, 6.1, 6.8, 7.4, 8.0, 8.9]
        ax.scatter(xs, [2.1 + 0.8 * x + (0.9 if i % 3 == 0 else -0.6) for i, x in enumerate(xs)], color="#5cb85c")
        ax.set_title("Ad spend vs. revenue")
        ax.set_xlabel("Ad spend ($k)")
        ax.set_ylabel("Revenue ($k)")

    for name, draw, expect in [("bar", bar, "bar chart"), ("line", line, "line chart"), ("pie", pie, "pie chart"), ("scatter", scatter, "scatter plot")]:
        add("image", f"{expect.capitalize()}: {name} data", expect, image=png(figure(draw), "image", f"{name}.png"))


def audio_voicemails() -> None:
    calls = [
        ("billing", "Billing: charged twice", "billing question", FEMALE,
         "Hi, this is Dana Kim. I just looked at my card statement and I was charged twice for this month. Could someone call me back about a refund? Thanks."),
        ("cancel", "Cancel: moving abroad", "cancel subscription", MALE,
         "Hello, my name is Tom. I'm moving abroad next month, so I'd like to cancel my subscription and stop any future payments. Please confirm by email."),
        ("support", "Support: app crashes", "technical support", FEMALE,
         "Hi, the app keeps crashing every time I try to upload a photo. I've reinstalled it twice and it still closes straight away. Can someone help me fix it?"),
        ("sales", "Sales: team plan pricing", "sales inquiry", MALE,
         "Good morning, I run a design studio with about fifty people and we're interested in your team plan. Could a salesperson send me pricing and set up a demo?"),
    ]
    for name, label, expect, voice, words in calls:
        add("audio", label, expect, audio=speech(words, voice, out("audio", f"{name}.wav")))


def installer(pct: int, status: str | None = None, color: str = "#222") -> Img:
    img, d = window("Acme Studio Setup")
    if status is None:
        write(d, (60, 100), f"Installing Acme Studio...\n{pct}% complete")
    else:
        write(d, (60, 100), status, fill=color, bold=True)
    progress(d, pct, color="#d9534f" if color == "#b91c1c" else "#2ea44f")
    return img


def video_installs() -> None:
    done = installer(100, "✓ Installation complete\nAcme Studio is ready to use.", "#1a7f37")
    failed = installer(45, "✗ Error 1603: installation failed\nSetup could not write to C:\\Program Files.", "#b91c1c")
    for name, label, expect, scenes in [
        ("succeeded", "Succeeded: finishes cleanly", "succeeded", [installer(20), installer(60), installer(90), done]),
        ("failed", "Failed: error 1603 halfway", "failed", [installer(15), installer(45), failed, failed]),
        ("running", "Still running: 70% when the clip ends", "still running", [installer(10), installer(30), installer(50), installer(70)]),
    ]:
        add("video", label, expect, video=clip(scenes, out("video", f"{name}.mp4")))


def receipt(shop: str, lines: list[tuple[str, str]], total: str, footer: str) -> Img:
    img, d = canvas("#e9e4da", 400, 560)
    d.rectangle((30, 20, 370, 540), fill="white", outline="#ccc")
    write(d, (50, 40), shop, 22, bold=True)
    y = 110
    for item, price in lines:
        write(d, (50, y), item, 18)
        d.text((350, y), price, font=font(18), fill="#222", anchor="ra")
        y += 34
    d.line((50, y + 6, 350, y + 6), fill="#888", width=2)
    write(d, (50, y + 20), "TOTAL", 20, bold=True)
    d.text((350, y + 20), total, font=font(20, True), fill="#222", anchor="ra")
    write(d, (50, 470), footer, 15, "#666")
    return img


def text_image_receipts() -> None:
    for name, label, expect, note, img in [
        ("meals", "Meals: client dinner", "meals", "Expense note: dinner with the Contoso team after the pitch, 3 people.",
         receipt("Trattoria Roma\n12 Hanover St, Boston", [("3x Tagliatelle", "$66.00"), ("1x Chianti (bottle)", "$48.00"), ("3x Tiramisu", "$27.00"), ("Service", "$21.15")],
                 "$162.15", "Table 7 · 19:42 · Thank you!")),
        ("travel", "Travel: train to a client site", "travel", "Expense note: train to the Boston client site for the kickoff.",
         receipt("Amtrak\nNortheast Regional", [("New York Penn → Boston", ""), ("Coach, seat 12C", "$89.00"), ("Booking fee", "$4.00")],
                 "$93.00", "Train 171 · Departs 07:05 · Ticket 4F2K9Q")),
        ("lodging", "Lodging: hotel for the offsite", "lodging", "Expense note: two nights for the Boston offsite.",
         receipt("Harbor View Hotel\nGuest folio", [("Room, 2 nights @ $189", "$378.00"), ("City tax", "$44.35"), ("Wi-Fi", "$0.00")],
                 "$422.35", "Check-in 10 Mar · Check-out 12 Mar")),
        ("office", "Office supplies: printer paper and toner", "office supplies", "Expense note: restocking the office printer.",
         receipt("Staples #0417", [("Copy paper, 5 reams", "$32.95"), ("HP 58A toner", "$94.99"), ("Sticky notes, 12 pk", "$8.49")],
                 "$136.43", "Store 0417 · Register 3 · 14:08")),
    ]:
        add("text-image", label, expect, text=note, image=png(img, "text-image", f"{name}.png"))


def text_audio_replies() -> None:
    for name, label, expect, agent, reply, voice in [
        ("confirms", "Confirms the order", "confirms the order",
         "Agent: Just to confirm, order 2291 is one large pepperoni pizza and a garlic bread, delivered to 14 Elm Street. Shall I place it?",
         "Yes, that's all correct. Go ahead and place it, thanks.", MALE),
        ("changes", "Wants changes: different quantity and day", "wants changes",
         "Agent: So that's order 1042, two standing desks, delivered on Tuesday. Shall I place it?",
         "Almost. Can you make it three desks instead of two, and deliver on Thursday rather than Tuesday?", FEMALE),
        ("cancels", "Cancels the order", "cancels the order",
         "Agent: To confirm, order 3310 is a pair of running shoes, size 42, arriving Friday. Shall I place it?",
         "Actually, no. Please cancel the whole order, I've found them somewhere else.", MALE),
    ]:
        add("text-audio", label, expect, text=agent, audio=speech(reply, voice, out("text-audio", f"{name}.wav")))


def editor(overlay: str | None = None) -> Img:
    img, d = window("Reports · Q3 summary.doc")
    d.rectangle((0, 40, W, 80), fill="#e7e7e7")
    for i, m in enumerate(["File", "Edit", "View", "Export"]):
        write(d, (16 + i * 90, 50), m, 18, bold=m == "Export" and overlay == "menu")
    for y in range(110, 330, 28):
        d.rectangle((60, y, 60 + (480 if y % 56 else 360), y + 10), fill="#cfcfcf")
    if overlay == "menu":
        d.rectangle((286, 80, 486, 160), fill="white", outline="#888")
        d.rectangle((288, 82, 484, 118), fill="#dbe7fb")
        write(d, (300, 88), "Export as PDF", 18)
        write(d, (300, 126), "Export as Word", 18)
    elif overlay == "busy":
        d.rounded_rectangle((170, 140, 470, 230), 10, fill="white", outline="#888")
        write(d, (200, 170), "Exporting PDF...", 20)
    elif overlay == "error":
        d.rounded_rectangle((140, 120, 500, 260), 10, fill="white", outline="#b91c1c", width=3)
        write(d, (170, 140), "✗ Export failed", 22, "#b91c1c", True)
        write(d, (170, 180), "Something went wrong. Try again.", 17)
        button(d, (390, 214, 480, 248), "OK", True)
    elif overlay == "saved":
        d.rounded_rectangle((170, 280, 470, 330), 10, fill="#1a7f37")
        write(d, (190, 292), "✓ Saved Q3 summary.pdf", 18, "white", True)
    return img


def text_video_repros() -> None:
    report = "Bug: clicking Export > Export as PDF shows an 'Export failed' error instead of saving the file."
    for name, label, expect, last in [("reproduced", "Reproduced: the error appears", "reproduced", "error"),
                                      ("not-reproduced", "Not reproduced: the PDF saves", "not reproduced", "saved")]:
        scenes = [editor(), editor("menu"), editor("busy"), editor(last)]
        add("text-video", label, expect, text=report, video=clip(scenes, out("text-video", f"{name}.mp4")))


def text_image_audio_tickets() -> None:
    def invoice() -> Img:
        img, d = window("Billing · Invoices")
        for i, (date, item, amount) in enumerate([("03 Sep", "Pro plan, September", "$29.00"), ("03 Sep", "Pro plan, September", "$29.00"), ("03 Aug", "Pro plan, August", "$29.00")]):
            y = 80 + i * 50
            d.rectangle((40, y, 600, y + 40), fill="#fff3cd" if i < 2 else "white", outline="#ddd")
            write(d, (56, y + 9), f"{date}    {item}", 18)
            d.text((584, y + 9), amount, font=font(18), fill="#222", anchor="ra")
        write(d, (40, 250), "2 charges on 03 Sep", 18, "#b45309", True)
        return img

    def login() -> Img:
        img, d = window("Sign in")
        write(d, (180, 70), "Welcome back", 24, bold=True)
        for y, v in [(120, "jo@northwind.com"), (170, "••••••••••")]:
            d.rectangle((180, y, 460, y + 36), fill="white", outline="#888")
            write(d, (192, y + 7), v, 18)
        write(d, (180, 222), "Account locked after 5 failed attempts.\nReset link sent, but sign-in is still blocked.", 15, "#b91c1c")
        button(d, (180, 290, 460, 326), "Sign in", True)
        return img

    def blank_chart() -> Img:
        img, d = window("Dashboard · Revenue")
        d.rectangle((40, 60, 600, 250), fill="white", outline="#ccc")
        write(d, (240, 140), "No data to display", 20, "#999")
        d.rectangle((40, 270, 600, 340), fill="#1e1e1e")
        write(d, (52, 282), "TypeError: Cannot read properties of\nundefined (reading 'map')  chart.js:214", 15, "#f87171")
        return img

    def settings() -> Img:
        img, d = window("Settings · Appearance")
        write(d, (60, 80), "Theme", 20, bold=True)
        d.rounded_rectangle((60, 120, 260, 160), 6, fill="white", outline="#2b579a", width=2)
        write(d, (80, 128), "● Light", 18)
        d.rounded_rectangle((280, 120, 480, 160), 6, fill="#eee", outline="#ccc")
        write(d, (300, 128), "Dark (not available)", 16, "#999")
        write(d, (60, 200), "Font size", 20, bold=True)
        write(d, (60, 236), "Medium", 18)
        return img

    for name, label, expect, subject, shot, voice, words in [
        ("billing", "Billing: charged twice", "billing", "Subject: charged twice for September", invoice(), FEMALE,
         "Hi, I can see two charges of twenty-nine dollars on the third of September. I only have one account, so could you refund one of them?"),
        ("access", "Account access: locked out", "account access", "Subject: can't sign in after resetting my password", login(), MALE,
         "I reset my password like the email said, but it still tells me my account is locked. I haven't been able to sign in since yesterday."),
        ("bug", "Bug report: blank revenue chart", "bug report", "Subject: revenue chart is empty since the update", blank_chart(), FEMALE,
         "Since this morning's update the revenue chart on the dashboard is just blank, and there's an error in the console. It worked fine last week."),
        ("feature", "Feature request: dark mode", "feature request", "Subject: please add a dark mode", settings(), MALE,
         "It would be great if you could add a dark mode. I work late and the white screen is really hard on my eyes. Everything else is great."),
    ]:
        add("text-image-audio", label, expect, text=subject, image=png(shot, "text-image-audio", f"{name}.png"),
            audio=speech(words, voice, out("text-image-audio", f"{name}.wav")))


def image_audio_commands() -> None:
    img, d = window("Budget.xlsx")
    d.rounded_rectangle((90, 80, 550, 300), 10, fill="white", outline="#888")
    write(d, (120, 105), "Do you want to save the changes\nyou made to Budget.xlsx?", 20, bold=True)
    write(d, (120, 180), "Your changes will be lost if you don't save them.", 15, "#555")
    for box, label, primary in [((120, 240, 240, 280), "Save", True), ((256, 240, 396, 280), "Don't Save", False), ((412, 240, 520, 280), "Cancel", False)]:
        button(d, box, label, primary)
    dialog = png(img, "image-audio", "dialog.png")
    for name, label, expect, voice, words in [
        ("save", "Save: keep my changes", "Save", FEMALE, "Yes, keep my changes, please."),
        ("dont-save", "Don't Save: throw them away", "Don't Save", MALE, "No, throw them away. I don't need any of those edits."),
        ("cancel", "Cancel: not done yet", "Cancel", FEMALE, "Wait, go back. I'm not finished with it yet."),
    ]:
        add("image-audio", label, expect, image=dialog, audio=speech(words, voice, out("image-audio", f"{name}.wav")))


def logo(d: Draw, x: int, y: int, s: float = 1.0, kind: str = "brightly") -> None:
    if kind == "brightly":  # an orange sun over a wordmark
        cx, cy, r = x + 30 * s, y + 30 * s, 30 * s
        for i in range(8):  # rays
            a = math.tau * i / 8
            d.line((cx + 1.2 * r * math.cos(a), cy + 1.2 * r * math.sin(a), cx + 1.6 * r * math.cos(a), cy + 1.6 * r * math.sin(a)), fill="#f59e0b", width=int(6 * s))
        d.ellipse((x, y, x + 60 * s, y + 60 * s), fill="#f59e0b")
        write(d, (int(x + 72 * s), int(y + 12 * s)), "Brightly", int(28 * s), "#f59e0b", True)
    elif kind == "wave":
        d.rounded_rectangle((x, y, x + 60 * s, y + 60 * s), int(12 * s), fill="#0ea5e9")
        write(d, (int(x + 72 * s), int(y + 12 * s)), "Wavecraft", int(28 * s), "#0ea5e9", True)
    else:
        d.polygon([(x, y + 60 * s), (x + 30 * s, y), (x + 60 * s, y + 60 * s)], fill="#16a34a")
        write(d, (int(x + 72 * s), int(y + 12 * s)), "Peakline", int(28 * s), "#16a34a", True)


def street(billboard: str | None, shift: int) -> Img:
    img, d = canvas("#bfe3f5")
    d.rectangle((0, 260, W, H), fill="#6b7280")
    for i, (x, h, c) in enumerate([(20, 150, "#d6c7b0"), (170, 190, "#c9b6a3"), (330, 130, "#e0d4c0"), (470, 170, "#cbbba5")]):
        d.rectangle((x - shift, 260 - h, x - shift + 140, 260), fill=c)
        for wy in range(270 - h, 250, 36):
            d.rectangle((x - shift + 20, wy, x - shift + 50, wy + 20), fill="#94a3b8")
    if billboard:
        d.rectangle((300 - shift, 30, 620 - shift, 130), fill="white", outline="#333", width=4)
        d.rectangle((455 - shift, 130, 465 - shift, 170), fill="#333")
        logo(d, 320 - shift, 50, 0.9, billboard)
    return img


def image_video_logos() -> None:
    ref, d = canvas("white", 360, 160)
    logo(d, 30, 50)
    reference = png(ref, "image-video", "logo.png")
    for name, label, expect, boards in [
        ("present", "Present: on a billboard mid-clip", "present", [None, "wave", "brightly", "brightly"]),
        ("absent", "Absent: only other brands appear", "absent", [None, "wave", "peak", "wave"]),
    ]:
        scenes = [street(b, i * 25) for i, b in enumerate(boards)]
        add("image-video", label, expect, image=reference, video=clip(scenes, out("image-video", f"{name}.mp4")))


def ad(scene: int, price: str) -> Img:
    img, d = canvas("#111827")
    d.ellipse((60, 90, 240, 270), outline="#e5e7eb", width=14)  # headphones: a band and two cups
    d.rectangle((50, 200, 90, 280), fill="#6366f1")
    d.rectangle((210, 200, 250, 280), fill="#6366f1")
    write(d, (290, 70), "Aurora", 44, "white", True)
    write(d, (290, 130), ["Wireless headphones", "40-hour battery", "Noise cancelling", "Order today"][scene], 24, "#c7d2fe")
    if scene >= 1:
        write(d, (290, 200), price, 64, "#facc15", True)
    return img


def audio_video_prices() -> None:
    for name, label, expect, said, voice in [
        ("match", "Prices match: $149 on screen and said", "prices match", "one hundred and forty-nine dollars", FEMALE),
        ("differ", "Prices differ: $149 on screen, $99 said", "prices differ", "just ninety-nine dollars", MALE),
    ]:
        vo = speech(f"Meet Aurora, our new wireless headphones. Forty hours of battery, and they're yours for {said}.",
                    voice, out("audio-video", f"{name}.vo.wav"))
        add("audio-video", label, expect, video=clip([ad(i, "$149") for i in range(4)], out("audio-video", f"{name}.mp4"), vo))
        vo.unlink()


def door(number: str, color: str, parcel: bool, person: str | None = None, stamp: str = "") -> Img:
    """A front door seen from a doorbell camera or a courier's photo, optionally with a parcel and a person."""
    img, d = canvas("#d6d3d1")
    d.rectangle((0, 280, W, H), fill="#78716c")
    d.rectangle((220, 40, 420, 290), fill=color, outline="#44403c", width=6)
    d.ellipse((390, 160, 404, 174), fill="#fbbf24")
    write(d, (300, 60), number, 30, "white", True)
    d.rectangle((190, 290, 450, 310), fill="#a16207")  # doormat
    if parcel:
        d.rectangle((270, 230, 370, 292), fill="#b45309", outline="#78350f", width=3)
        d.line((270, 250, 370, 250), fill="#fde68a", width=6)
    if person:  # a stick figure approaching, or carrying the parcel away
        x = 500 if person == "near" else 560
        d.ellipse((x, 100, x + 40, 140), fill="#1f2937")
        d.rectangle((x + 8, 140, x + 32, 240), fill="#1f2937")
        d.line((x + 12, 240, x, 290), fill="#1f2937", width=8)
        d.line((x + 28, 240, x + 40, 290), fill="#1f2937", width=8)
        if person == "carry":
            d.rectangle((x - 30, 170, x + 20, 205), fill="#b45309")
    if stamp:
        d.rectangle((0, 0, 230, 34), fill="#000")
        write(d, (10, 6), stamp, 17, "white")
    return img


def text_image_video_parcels() -> None:
    claim = "Customer: the app says my parcel was delivered at 2:14 pm, but I can't find it anywhere."
    delivered_here = door("14", "#1d4ed8", True, stamp="Delivered 2:14 PM")
    for name, label, expect, photo, frames in [
        ("never", "Never delivered: photo shows another door", "never delivered", door("41", "#b91c1c", True, stamp="Delivered 2:14 PM"),
         [door("14", "#1d4ed8", False, stamp=f"Front door · {t}") for t in ["1:30 PM", "2:10 PM", "2:30 PM", "4:00 PM"]]),
        ("stolen", "Stolen after delivery: someone takes it", "stolen after delivery", delivered_here,
         [door("14", "#1d4ed8", True, stamp="Front door · 2:15 PM"), door("14", "#1d4ed8", True, "near", "Front door · 2:41 PM"),
          door("14", "#1d4ed8", False, "carry", "Front door · 2:42 PM"), door("14", "#1d4ed8", False, stamp="Front door · 3:30 PM")]),
        ("at-door", "Still at the door: never moved", "still at the door", delivered_here,
         [door("14", "#1d4ed8", True, stamp=f"Front door · {t}") for t in ["2:15 PM", "3:30 PM", "5:00 PM", "6:45 PM"]]),
    ]:
        add("text-image-video", label, expect, text=claim, image=png(photo, "text-image-video", f"{name}.png"),
            video=clip(frames, out("text-image-video", f"{name}.mp4")))


def slide(title: str, body: str) -> Img:
    img, d = canvas("white")
    d.rectangle((0, 0, W, 70), fill="#4f46e5")
    write(d, (30, 18), title, 28, "white", True)
    write(d, (40, 110), body, 26)
    write(d, (500, 320), "Acme · Q3", 16, "#999")
    return img


def text_audio_video_claims() -> None:
    scenes = [slide("Q3 update", "Northwind Analytics\nQuarterly business review"),
              slide("Revenue", "Revenue grew 12% quarter on quarter\nto $48 million"),
              slide("Product", "Nimbus launch moves to March\nto finish security review"),
              slide("Thank you", "Questions?")]
    vo = speech("Welcome to our Q3 update. Revenue grew twelve percent this quarter, to forty-eight million dollars. "
                "We've moved the Nimbus launch to March so we can finish the security review. Thank you.", FEMALE, out("text-audio-video", "talk.vo.wav"))
    talk = clip(scenes, out("text-audio-video", "talk.mp4"), vo)
    vo.unlink()
    for label, expect, claim in [
        ("Supported: revenue grew 12%", "supported", "Claim: the company's revenue grew by 12% last quarter."),
        ("Refuted: revenue fell", "refuted", "Claim: the company reported that revenue fell last quarter."),
        ("Not enough information: hiring plans", "not enough information", "Claim: the company plans to hire 200 engineers next year."),
    ]:
        add("text-audio-video", label, expect, text=claim, video=talk)


def mug(d: Draw, x: int, y: int, color: str = "#2563eb", broken: bool = False) -> None:
    d.rounded_rectangle((x, y, x + 120, y + 140), 14, fill=color)
    if broken:  # the handle lies beside the mug and a crack runs down the side
        d.arc((x + 150, y + 90, x + 210, y + 150), 0, 360, fill=color, width=14)
        d.line([(x + 50, y), (x + 65, y + 40), (x + 45, y + 80), (x + 62, y + 140)], fill="#111", width=5)
    else:
        d.arc((x + 95, y + 30, x + 165, y + 100), 270, 90, fill=color, width=14)


def teapot(d: Draw, x: int, y: int) -> None:
    d.ellipse((x, y + 20, x + 160, y + 150), fill="#dc2626")
    d.polygon([(x + 150, y + 70), (x + 215, y + 40), (x + 160, y + 110)], fill="#dc2626")
    d.rectangle((x + 60, y, x + 100, y + 24), fill="#dc2626")


def unboxing(stage: int, item: str) -> Img:
    img, d = canvas("#e7e5e4")
    d.rectangle((0, 250, W, H), fill="#a8a29e")  # table
    if stage == 0:
        d.rectangle((200, 110, 440, 270), fill="#c2a36b", outline="#8b6d3f", width=4)
        d.rectangle((200, 170, 440, 186), fill="#e5e7eb")  # tape
    elif stage == 1:
        d.polygon([(200, 150), (240, 90), (440, 90), (440, 150)], fill="#d6bb85")
        d.rectangle((200, 150, 440, 270), fill="#c2a36b", outline="#8b6d3f", width=4)
    else:
        d.rectangle((60, 190, 200, 270), fill="#c2a36b", outline="#8b6d3f", width=4)  # empty box to the side
        if item == "teapot":
            teapot(d, 300, 100)
        else:
            mug(d, 300, 110, broken=item == "broken")
    return img


def image_audio_video_returns() -> None:
    listing, d = canvas("white", 480, 360)
    mug(d, 150, 90)
    write(d, (30, 20), "Blue ceramic mug · 350 ml", 22, bold=True)
    write(d, (30, 300), "$18.00 · Dishwasher safe", 18, "#555")
    photo = png(listing, "image-audio-video", "listing.png")
    for name, label, expect, item, voice, words in [
        ("as-described", "As described: changed my mind", "item as described", "mug", FEMALE,
         "Okay, opening it now. It's the blue mug, and it looks just like the photo. I've just changed my mind, so I'd like to return it."),
        ("damaged", "Damaged: handle snapped off", "item damaged", "broken", MALE,
         "Let's see. Oh no, the handle has snapped right off, and there's a crack all the way down the side of the mug."),
        ("wrong", "Wrong item: a red teapot", "wrong item", "teapot", FEMALE,
         "Hmm, this isn't what I ordered at all. I bought a blue mug, and this is a red teapot."),
    ]:
        vo = speech(words, voice, out("image-audio-video", f"{name}.vo.wav"))
        scenes = [unboxing(0, item), unboxing(1, item), unboxing(2, item), unboxing(2, item)]
        add("image-audio-video", label, expect, image=photo, video=clip(scenes, out("image-audio-video", f"{name}.mp4"), vo))
        vo.unlink()


def status_page(banner: str, color: str, rows: list[tuple[str, str, str]]) -> Img:
    img, d = window("status.northwind.com", bar="#374151")
    d.rounded_rectangle((30, 60, 610, 120), 8, fill=color)
    write(d, (50, 76), banner, 22, "white", True)
    for i, (svc, state, c) in enumerate(rows):
        y = 140 + i * 50
        d.rectangle((30, y, 610, y + 42), fill="white", outline="#ddd")
        write(d, (46, y + 10), svc, 18)
        d.text((594, y + 10), state, font=font(18, True), fill=c, anchor="ra")
    return img


def dashboard(title: str, values: list[float], unit: str, limit: float) -> Img:
    def draw(ax: plt.Axes) -> None:
        ax.plot(range(len(values)), values, color="#dc2626", linewidth=2.5)
        ax.axhline(limit, color="#9ca3af", linestyle="--")
        ax.set_title(title)
        ax.set_ylabel(unit)
        ax.set_xticks([0, len(values) // 2, len(values) - 1], ["-30 min", "-15 min", "now"])
    return figure(draw)


def text_image_audio_video_incidents() -> None:
    ok, degraded, down = ("Operational", "#16a34a"), ("Degraded", "#d97706"), ("Major outage", "#b91c1c")

    def rows(checkout: tuple[str, str], search: tuple[str, str]) -> list[tuple[str, str, str]]:
        return [("Checkout", *checkout), ("Search", *search), ("Accounts", *ok), ("Reporting (internal)", *ok)]

    for name, label, expect, alert, dash, page, voice, words in [
        ("sev1", "SEV1: checkout is down", "SEV1: outage, customers blocked",
         "Alert: checkout-api error rate at 100% for 10 minutes; every payment attempt fails.",
         dashboard("checkout-api error rate", [0.4] * 18 + [35, 88, 100, 100, 100, 100, 100, 100], "% of requests", 5),
         status_page("Major outage: Checkout", "#b91c1c", rows(down, ok)), MALE,
         "This is Sam on call. Checkout is completely down. No customer can pay right now. We're rolling back the last deploy."),
        ("sev2", "SEV2: search is slow", "SEV2: degraded, customers affected",
         "Alert: search-api p95 latency 4.8 s for 15 minutes (normal: 300 ms).",
         dashboard("search-api p95 latency", [0.3] * 12 + [1.2, 2.5, 3.9, 4.6, 4.8, 4.7, 4.9, 4.8, 4.8, 4.6, 4.8, 4.7], "seconds", 1),
         status_page("Degraded performance: Search", "#d97706", rows(ok, degraded)), FEMALE,
         "Hi, it's Maya. Search is really slow for a lot of customers, but it's still returning results. We're adding capacity now."),
        ("sev3", "SEV3: internal report delayed", "SEV3: minor, no customer impact",
         "Alert: nightly-export job failed; internal finance report delayed.",
         dashboard("nightly-export failures", [0] * 22 + [1, 1], "failed runs", 0.5),
         status_page("All systems operational", "#16a34a", rows(ok, ok)), MALE,
         "Hey, it's Sam. It's only the internal export job. Customers aren't affected at all. I'll rerun it in the morning."),
    ]:
        vo = speech(words, voice, out("text-image-audio-video", f"{name}.vo.wav"))
        add("text-image-audio-video", label, expect, text=alert, image=png(dash, "text-image-audio-video", f"{name}.png"),
            video=clip([page] * 4, out("text-image-audio-video", f"{name}.mp4"), vo))
        vo.unlink()


def check() -> None:
    """Every expected answer must be one of its Jev's options, and every media file must exist."""
    for jev, examples in EXAMPLES.items():
        options = set(re.findall(r'^\s+\w+ = "([^"]+)"$', (ROOT / jev / "jev.py").read_text(), re.M))
        for ex in examples:
            assert ex["expect"] in options, f"{jev}: {ex['expect']!r} is not one of {sorted(options)}"
            for k in ("image", "audio", "video"):
                assert k not in ex or (HERE / ex[k]).exists(), f"{jev}: missing {ex[k]}"


if __name__ == "__main__":
    for make in [text_emails, image_charts, audio_voicemails, video_installs, text_image_receipts, text_audio_replies, text_video_repros,
                 image_audio_commands, image_video_logos, audio_video_prices, text_image_audio_tickets, text_image_video_parcels,
                 text_audio_video_claims, image_audio_video_returns, text_image_audio_video_incidents]:
        print(f"· {make.__name__}")
        make()
    check()
    (HERE / "examples.json").write_text(json.dumps(EXAMPLES, indent=1, ensure_ascii=False) + "\n")
    print(f"{sum(map(len, EXAMPLES.values()))} examples for {len(EXAMPLES)} Jevs -> {HERE.relative_to(ROOT)}/examples.json")
