import ctypes
import math
import time
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageDraw, ImageTk

LIGHT = {
    "bg": "#FFFFFF", "card": "#F6F8FA", "border": "#D1D9E0", "text": "#1F2328",
    "muted": "#59636E", "faint": "#656D76", "link": "#0969DA", "hover": "#EEF1F4",
    "field": "#FFFFFF", "green": "#1A7F37", "red": "#CF222E", "yellow": "#9A6700",
}
DARK = {
    "bg": "#0D1117", "card": "#151B23", "border": "#30363D", "text": "#E6EDF3",
    "muted": "#9198A1", "faint": "#7D8590", "link": "#4493F8", "hover": "#1C232D",
    "field": "#0D1117", "green": "#3FB950", "red": "#F85149", "yellow": "#D29922",
}
GRADIENT = ("#22D3EE", "#8B5CF6")
VIOLET = "#8B5CF6"
DOT = {"ok": "#3FB950", "error": "#F85149", "warning": "#D29922", "neutral": "#8C959F"}

FONT = "Segoe UI"
MONO_FONT = "Consolas"


def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


WINDOW_ICON = None
_loaded_icons = []


def set_taskbar_icon(window):
    if WINDOW_ICON is None:
        return
    try:
        u = ctypes.windll.user32
        u.LoadImageW.restype = ctypes.c_void_p
        u.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_uint]
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        hwnd = u.GetParent(window.winfo_id())
        for icon_type, metric in ((1, 11), (0, 49)):
            size = u.GetSystemMetrics(metric)
            h = u.LoadImageW(None, str(WINDOW_ICON), 1, size, size, 0x10)
            if h:
                _loaded_icons.append(h)
                u.SendMessageW(hwnd, 0x80, icon_type, h)
    except (AttributeError, OSError, tk.TclError):
        pass


def windows_dark_mode():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    a, b = _rgb(c1), _rgb(c2)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


PULSE_CYCLE = 2.0
PULSE_FRAMES = 120


def _pulse_frame(color, f, scale, ss=4):
    stroke = max(1.0, 1.5 * scale)
    side = int(math.ceil(2 * (10 * scale + stroke))) + 2
    big = side * ss
    c = big / 2
    rgb = _rgb(color)

    ring = Image.new("RGBA", (big, big), rgb + (0,))
    eased = 1 - (1 - f) ** 3
    r = (4 + 6 * eased) * scale * ss + stroke * ss / 2
    ImageDraw.Draw(ring).ellipse((c - r, c - r, c + r, c + r), outline=rgb + (255,), width=max(1, round(stroke * ss)))
    ring = ring.resize((side, side), Image.LANCZOS)
    opacity = 0.8 * (1 - f)
    ring.putalpha(ring.getchannel("A").point(lambda v: round(v * opacity)))

    dot = Image.new("RGBA", (big, big), rgb + (0,))
    rd = 4 * scale * ss
    ImageDraw.Draw(dot).ellipse((c - rd, c - rd, c + rd, c + rd), fill=rgb + (255,))
    dot = dot.resize((side, side), Image.LANCZOS)
    return Image.alpha_composite(ring, dot)


def _gradient(w, h, colors):
    row = Image.new("RGBA", (max(w, 2), 1))
    for x in range(row.width):
        row.putpixel((x, 0), _rgb(mix(colors[0], colors[1], x / (row.width - 1))) + (255,))
    return row.resize((w, h))


def rounded_shape(w, h, radius, fill=None, border=None, gradient=None, border_width=1, ss=4):
    W, H, R = w * ss, h * ss, radius * ss
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], R, fill=255)
    base = _gradient(W, H, gradient) if gradient else Image.new("RGBA", (W, H), _rgb(fill) + (255,))
    img.paste(base, (0, 0), mask)
    if border:
        e = border_width * ss
        ImageDraw.Draw(img).rounded_rectangle([e / 2, e / 2, W - 1 - e / 2, H - 1 - e / 2], R - e / 2,
                                              outline=_rgb(border) + (255,), width=e)
    return img.resize((w, h), Image.LANCZOS)


def _draw_icon(name, d, k, color, w):
    def p(x, y):
        return (x * k, y * k)

    def line(*pts):
        pts = [p(*q) for q in pts]
        d.line(pts, fill=color, width=w, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=color)

    def arc(cx, cy, r, start, end):
        d.arc([p(cx - r, cy - r), p(cx + r, cy + r)], start, end, fill=color, width=w)

    def ellipse(x0, y0, x1, y1):
        d.ellipse([p(x0, y0), p(x1, y1)], outline=color, width=w)

    if name == "document":
        line((14, 2), (6, 2))
        arc(6, 4, 2, 180, 270)
        line((4, 4), (4, 20))
        arc(6, 20, 2, 90, 180)
        line((6, 22), (18, 22))
        arc(18, 20, 2, 0, 90)
        line((20, 20), (20, 8), (14, 2))
        line((14, 2), (14, 8), (20, 8))
        line((8, 13), (16, 13))
        line((8, 17), (16, 17))
        line((8, 9), (10, 9))
    elif name == "folder":
        line((4.5, 5), (9, 5), (11, 7.5), (19.5, 7.5), (21, 9), (21, 18.5), (19.5, 20),
             (4.5, 20), (3, 18.5), (3, 6.5), (4.5, 5))
    elif name == "layers":
        line((12, 3), (2, 8), (12, 13), (22, 8), (12, 3))
        line((2, 13), (12, 18), (22, 13))
        line((2, 17.5), (12, 22.5), (22, 17.5))
    elif name == "refresh":
        arc(12, 12, 9, 185, 320)
        line((21, 3), (21, 8), (16, 8))
        arc(12, 12, 9, 5, 140)
        line((3, 21), (3, 16), (8, 16))
    elif name == "sliders":
        for y, a, b in ((4, 14, 10), (12, 12, 8), (20, 16, 12)):
            line((21, y), (a, y))
            line((b, y), (3, y))
        line((14, 2), (14, 6))
        line((8, 10), (8, 14))
        line((16, 18), (16, 22))
    elif name == "database":
        ellipse(3, 2, 21, 8)
        line((3, 5), (3, 19))
        line((21, 5), (21, 19))
        d.arc([p(3, 9), p(21, 15)], 0, 180, fill=color, width=w)
        d.arc([p(3, 16), p(21, 22)], 0, 180, fill=color, width=w)
    elif name == "arrow":
        line((5, 12), (19, 12))
        line((12, 5), (19, 12), (12, 19))
    elif name == "info":
        ellipse(2, 2, 22, 22)
        line((12, 16), (12, 12))
        r = w * 0.65
        cx, cy = p(12, 8)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    elif name == "user":
        ellipse(8, 4, 16, 12)
        arc(12, 21, 8, 180, 360)
    elif name == "phone":
        d.rounded_rectangle([p(5, 2), p(19, 22)], radius=2.5 * k, outline=color, width=w)
        line((11, 18), (13, 18))


def pbtec_logo(height, light_color, path):
    img = Image.open(path).convert("RGB")
    result = Image.new("RGBA", img.size)
    light_color = _rgb(light_color)
    pixels = []
    data = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    for r, g, b in data:
        a = max(r, g, b)
        if a < 24:
            pixels.append((0, 0, 0, 0))
        elif r > 90 and r > g * 1.8 and r > b * 1.8:
            pixels.append((round(r * 255 / a), round(g * 255 / a), round(b * 255 / a), a))
        else:
            pixels.append(light_color + (a,))
    result.putdata(pixels)
    result = result.crop(result.getbbox())
    width = max(1, round(result.width * height / result.height))
    return result.resize((width, height), Image.LANCZOS)


def transparent_logo(height, path):
    img = Image.open(path).convert("RGBA")
    img = img.crop(img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())
    width = max(1, round(img.width * height / img.height))
    return img.resize((width, height), Image.LANCZOS)


def icon(name, color, size, ss=8):
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _draw_icon(name, ImageDraw.Draw(img), S / 24, _rgb(color) + (255,), max(1, round(2 * S / 24)))
    return img.resize((size, size), Image.LANCZOS)


class Theme:
    def __init__(self, window, dark=None):
        self.dark = windows_dark_mode() if dark is None else dark
        self.c = DARK if self.dark else LIGHT
        self.scale = max(1.0, window.winfo_fpixels("1i") / 96)
        self._images = {}
        self.fonts = {
            "label": tkfont.Font(window, family=MONO_FONT, size=9),
            "title": tkfont.Font(window, family=FONT, size=22, weight="bold"),
            "subtitle": tkfont.Font(window, family=FONT, size=11),
            "section": tkfont.Font(window, family=FONT + " Semibold", size=12),
            "body": tkfont.Font(window, family=FONT, size=10),
            "small": tkfont.Font(window, family=FONT, size=9),
            "strong": tkfont.Font(window, family=FONT + " Semibold", size=11),
            "button": tkfont.Font(window, family=FONT + " Semibold", size=10),
            "number": tkfont.Font(window, family=FONT + " Semibold", size=16),
        }

    def px(self, v):
        return int(round(v * self.scale))

    def photo(self, key, create):
        if key not in self._images:
            self._images[key] = ImageTk.PhotoImage(create())
        return self._images[key]

    def icon(self, name, color=VIOLET, size=18):
        s = self.px(size)
        return self.photo(("ic", name, color, s), lambda: icon(name, color, s))

    def logo(self, height):
        from database import RESOURCES

        h = self.px(height)
        if not self.dark:
            light = RESOURCES / "resources" / "pbtec_logo_light.png"
            if light.exists():
                return self.photo(("logo-light", h), lambda: transparent_logo(h, light))
        path = RESOURCES / "resources" / "pbtec_logo.png"
        if not path.exists():
            return None
        color = "#FFFFFF" if self.dark else self.c["text"]
        return self.photo(("logo", h, color), lambda: pbtec_logo(h, color, path))

    def setup_window(self, window, title):
        window.title(title)
        window.configure(bg=self.c["bg"])
        window.resizable(False, False)
        window.update_idletasks()
        set_taskbar_icon(window)
        if self.dark:
            try:
                hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
                value = ctypes.c_int(1)
                for attribute in (20, 19):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), 4)
            except (AttributeError, OSError):
                pass

    def label(self, parent, text="", font="body", color="text", bg="bg", **kw):
        return tk.Label(parent, text=text, font=self.fonts[font], fg=self.c.get(color, color),
                        bg=self.c.get(bg, bg), **kw)

    def frame(self, parent, bg="bg", **kw):
        return tk.Frame(parent, bg=self.c.get(bg, bg), **kw)


class Header(tk.Canvas):
    def __init__(self, parent, theme, width, label, title, subtitle, with_status=True, with_logo=True):
        t = theme
        self.t = t
        height = t.px(122 if with_status else 104)
        super().__init__(parent, width=width, height=height, bg=t.c["bg"], highlightthickness=0, bd=0)
        logo = t.logo(96 if with_status else 84) if with_logo else None
        if logo is not None:
            self.create_image(width, t.px(2), image=logo, anchor="ne")
        x = 0
        spacing = t.px(2.5)
        for ch in label.upper():
            self.create_text(x, t.px(6), text=ch, anchor="nw", font=t.fonts["label"], fill=t.c["muted"])
            x += t.fonts["label"].measure(ch) + spacing
        self.create_text(-t.px(2), t.px(22), text=title, anchor="nw", font=t.fonts["title"], fill=t.c["text"])
        self.create_text(0, t.px(66), text=subtitle, anchor="nw", font=t.fonts["subtitle"], fill=t.c["muted"])
        y = t.px(100)
        bar = t.photo(("bar", t.px(56)), lambda: rounded_shape(t.px(56), max(2, t.px(3)), max(1, t.px(1.5)),
                                                               gradient=GRADIENT))
        self.create_image(0, y, image=bar, anchor="w")
        self._phase = 0
        self._color = DOT["ok"]
        if with_status:
            cx = t.px(80)
            self._cx, self._cy = cx, y
            self._frames = {}
            self._start = time.perf_counter()
            self._pulse_item = self.create_image(cx, y, image=self._frame(0), anchor="center")
            zone = t.px(12)
            self.create_rectangle(cx - zone, y - zone, cx + zone, y + zone, outline="", fill="", tags=("status",))
            self.tag_raise("status")
            self._tooltip_text = ""
            self._tooltip = None
            self.tag_bind("status", "<Enter>", self._show_tooltip)
            self.tag_bind("status", "<Leave>", self._hide_tooltip)
            self._animation = self.after(16, self._pulse)
            self.bind("<Destroy>", lambda _e: (self.after_cancel(self._animation), self._hide_tooltip()))

    def status(self, text, kind="ok"):
        self._color = DOT.get(kind, DOT["neutral"])
        self._phase = -1
        self._draw_pulse()
        self._tooltip_text = text
        if self._tooltip is not None:
            self._hide_tooltip()
            self._show_tooltip()

    def _show_tooltip(self, _event=None):
        if not self._tooltip_text or self._tooltip is not None:
            return
        t = self.t
        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=t.c["border"])
        tk.Label(tip, text=self._tooltip_text, font=t.fonts["small"], fg=t.c["text"], bg=t.c["card"],
                 padx=t.px(10), pady=t.px(5)).pack(padx=1, pady=1)
        x = self.winfo_rootx() + self._cx + t.px(14)
        y = self.winfo_rooty() + self._cy - t.px(14)
        tip.geometry(f"+{x}+{y}")
        self._tooltip = tip

    def _hide_tooltip(self, _event=None):
        if self._tooltip is not None:
            try:
                self._tooltip.destroy()
            except tk.TclError:
                pass
            self._tooltip = None

    def _frame(self, i):
        key = (self._color, i)
        photo = self._frames.get(key)
        if photo is None:
            img = _pulse_frame(self._color, i / PULSE_FRAMES, self.t.scale)
            photo = self._frames[key] = ImageTk.PhotoImage(img, master=self)
        return photo

    def _draw_pulse(self):
        phase = ((time.perf_counter() - self._start) % PULSE_CYCLE) / PULSE_CYCLE
        i = int(phase * PULSE_FRAMES) % PULSE_FRAMES
        if i != self._phase:
            self._phase = i
            self.itemconfig(self._pulse_item, image=self._frame(i))

    def _pulse(self):
        self._draw_pulse()
        self._animation = self.after(8, self._pulse)


class Button(tk.Canvas):
    def __init__(self, parent, theme, text, command, icon=None, primary=False, height=40, bg="bg", width=None):
        t = self.t = theme
        self.command = command
        self.enabled = True
        h = t.px(height)
        font = t.fonts["button"]
        icon_size = t.px(16) if icon else 0
        gap = t.px(8) if icon and text else 0
        content = icon_size + gap + font.measure(text)
        w = t.px(width) if width else content + t.px(40)
        super().__init__(parent, width=w, height=h, bg=t.c.get(bg, bg), highlightthickness=0, bd=0, cursor="hand2")

        r = h // 2
        if primary:
            text_color = "#FFFFFF"
            normal = t.photo(("bp", w, h), lambda: rounded_shape(w, h, r, gradient=GRADIENT))
            lighter = tuple(mix(c, "#FFFFFF", 0.15) for c in GRADIENT)
            hover = t.photo(("bph", w, h), lambda: rounded_shape(w, h, r, gradient=lighter))
            faded = tuple(mix(c, t.c["bg"], 0.55) for c in GRADIENT)
            disabled = t.photo(("bpi", w, h, t.dark), lambda: rounded_shape(w, h, r, gradient=faded))
            icon_color = "#FFFFFF"
        else:
            text_color = t.c["text"]
            normal = t.photo(("bs", w, h, t.dark), lambda: rounded_shape(w, h, r, t.c["card"], t.c["border"]))
            hover = t.photo(("bsh", w, h, t.dark), lambda: rounded_shape(w, h, r, t.c["hover"], t.c["border"]))
            disabled = normal
            icon_color = VIOLET
        self._images = {"normal": normal, "hover": hover, "disabled": disabled}
        self._bg_item = self.create_image(0, 0, image=normal, anchor="nw")
        x = (w - content) // 2
        if icon:
            self.create_image(x, h // 2, image=t.icon(icon, icon_color, 16), anchor="w")
            x += icon_size + gap
        self._text_item = self.create_text(x, h // 2, text=text, anchor="w", font=font, fill=text_color)
        self._text_color = text_color
        self.bind("<Enter>", lambda _e: self.enabled and self.itemconfig(self._bg_item, image=hover))
        self.bind("<Leave>", lambda _e: self.enabled and self.itemconfig(self._bg_item, image=normal))
        self.bind("<ButtonRelease-1>", self._click)

    def _click(self, event):
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        if self.enabled and inside and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.itemconfig(self._bg_item, image=self._images["normal" if enabled else "disabled"])
        self.itemconfig(self._text_item,
                        fill=self._text_color if enabled else mix(self._text_color, self.t.c["bg"], 0.4))
        self.config(cursor="hand2" if enabled else "arrow")


class Field(tk.Canvas):
    def __init__(self, parent, theme, width, height=40, font="body", show="", hint="", justify="left",
                 value="", bg="bg"):
        t = self.t = theme
        w, h = t.px(width), t.px(height)
        super().__init__(parent, width=w, height=h, bg=t.c.get(bg, bg), highlightthickness=0, bd=0)
        r = t.px(8)
        normal = t.photo(("cp", w, h, t.dark), lambda: rounded_shape(w, h, r, t.c["field"], t.c["border"]))
        focused = t.photo(("cpf", w, h, t.dark),
                          lambda: rounded_shape(w, h, r, t.c["field"], t.c["link"], border_width=2))
        self._bg_item = self.create_image(0, 0, image=normal, anchor="nw")
        self.hint, self._show, self._showing_hint = hint, show, False
        self.entry = tk.Entry(self, relief="flat", bd=0, highlightthickness=0, font=t.fonts[font],
                              bg=t.c["field"], fg=t.c["text"], insertbackground=t.c["text"],
                              justify=justify, show=show, disabledbackground=t.c["field"])
        m = t.px(12)
        self.create_window(m, h // 2, window=self.entry, anchor="w", width=w - 2 * m)
        self.entry.bind("<FocusIn>", lambda _e: (self.itemconfig(self._bg_item, image=focused), self._remove_hint()))
        self.entry.bind("<FocusOut>", lambda _e: (self.itemconfig(self._bg_item, image=normal), self._put_hint()))
        self.bind("<Button-1>", lambda _e: self.entry.focus_set())
        if value:
            self.entry.insert(0, value)
        self._put_hint()

    def _put_hint(self):
        if self.hint and not self.entry.get():
            self._showing_hint = True
            self.entry.config(show="", fg=self.t.c["faint"])
            self.entry.insert(0, self.hint)

    def _remove_hint(self):
        if self._showing_hint:
            self._showing_hint = False
            self.entry.delete(0, "end")
            self.entry.config(show=self._show, fg=self.t.c["text"])

    def get(self):
        return "" if self._showing_hint else self.entry.get().strip()

    def set(self, text):
        self._remove_hint()
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        if self.focus_get() is not self.entry:
            self._put_hint()

    def focus_entry(self):
        self.entry.focus_set()


def section_title(parent, theme, icon_name, text, bg="bg"):
    f = theme.frame(parent, bg)
    tk.Label(f, image=theme.icon(icon_name, VIOLET, 20), bg=theme.c[bg]).pack(side="left")
    theme.label(f, text, "section", bg=bg).pack(side="left", padx=(theme.px(8), 0))
    return f
