import ctypes
import tkinter as tk
from ctypes import wintypes

from PIL import Image

import theme as tm

_u32 = ctypes.WinDLL("user32")
_u32.GetForegroundWindow.restype = wintypes.HWND
_u32.SetForegroundWindow.argtypes = [wintypes.HWND]
_u32.GetAncestor.restype = wintypes.HWND
_u32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
_u32.GetAsyncKeyState.restype = ctypes.c_short
_u32.MonitorFromPoint.restype = wintypes.HMONITOR
_u32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_u32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(_MonitorInfo)]


def _work_area(x, y):
    try:
        mon = _u32.MonitorFromPoint(wintypes.POINT(x, y), 2)
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        if mon and _u32.GetMonitorInfoW(mon, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    except (AttributeError, OSError):
        pass
    return None


class MenuItem:
    def __init__(self, icon, title, description, action, is_on=None):
        self.icon, self.title, self.description = icon, title, description
        self.action, self.is_on = action, is_on


SEPARATOR = None


class TrayMenu:
    def __init__(self, root):
        self.root = root
        self.window = None

    def close(self, _event=None):
        if self.window is not None:
            window, self.window = self.window, None
            try:
                window.destroy()
            except tk.TclError:
                pass

    def show(self, status, items):
        self.close()
        t = self.t = tm.Theme(self.root)
        c = t.c
        self._status = status
        background = c["card"]
        hover_color = tm.mix(background, tm.VIOLET, 0.12 if t.dark else 0.08)
        title_font, desc_font = t.fonts["strong"], t.fonts["small"]

        w = self.window = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=c["border"])
        body = tk.Frame(w, bg=background)
        body.pack(padx=1, pady=1)

        outer, left, icon_w, gap, right = t.px(6), t.px(12), t.px(20), t.px(12), t.px(16)
        sw_w, sw_h = t.px(34), t.px(18)
        has_switch = any(o is not SEPARATOR and o.is_on for o in items)
        text_w = max(max(title_font.measure(o.title), desc_font.measure(o.description))
                     for o in items if o is not SEPARATOR)
        W = left + icon_w + gap + text_w + (sw_w + t.px(20) if has_switch else 0) + right
        title_h, desc_h = title_font.metrics("linespace"), desc_font.metrics("linespace")
        text_top = t.px(7)
        H = text_top + title_h + t.px(1) + desc_h + t.px(8)
        highlight = t.photo(("menu-hover", W, H, t.dark), lambda: tm.rounded_shape(W, H, t.px(6), hover_color))

        top = tk.Frame(body, bg=background)
        top.pack(fill="x", padx=(outer + left, outer + right), pady=(t.px(10), t.px(6)))
        self._dot = tk.Label(top, bg=background)
        self._dot.pack(side="left", padx=(t.px(5), t.px(15)))
        self._status_label = tk.Label(top, font=desc_font, fg=c["faint"], bg=background, anchor="w",
                                      justify="left", wraplength=W - left - icon_w - gap)
        self._status_label.pack(side="left", fill="x")
        self._update_status()

        for item in items:
            if item is SEPARATOR:
                tk.Frame(body, bg=c["border"], height=1).pack(fill="x", padx=outer + t.px(6), pady=t.px(4))
                continue
            cv = tk.Canvas(body, width=W, height=H, bg=background, highlightthickness=0, bd=0, cursor="hand2")
            cv.pack(padx=outer)
            bg_item = cv.create_image(0, 0, image=highlight, anchor="nw", state="hidden")
            title_middle = text_top + title_h // 2
            cv.create_image(left, title_middle, image=t.icon(item.icon, tm.VIOLET, 20), anchor="w")
            x = left + icon_w + gap
            cv.create_text(x, text_top, text=item.title, anchor="nw", font=title_font, fill=c["text"])
            cv.create_text(x, text_top + title_h + t.px(1), text=item.description, anchor="nw", font=desc_font,
                           fill=c["muted"])
            switch = None
            if item.is_on:
                switch = cv.create_image(W - right, H // 2, image=self._switch(item.is_on(), sw_w, sw_h), anchor="e")
            cv.bind("<Enter>", lambda _e, cv=cv, i=bg_item: cv.itemconfig(i, state="normal"))
            cv.bind("<Leave>", lambda _e, cv=cv, i=bg_item: cv.itemconfig(i, state="hidden"))
            cv.bind("<ButtonRelease-1>",
                    lambda e, item=item, cv=cv, sw=switch: self._click(e, item, cv, sw, sw_w, sw_h))
        tk.Frame(body, bg=background, height=t.px(6)).pack()

        w.bind("<Escape>", self.close)
        self._position()
        w.deiconify()
        w.update_idletasks()
        self._hwnd = _u32.GetAncestor(w.winfo_id(), 2)
        self._round_corners()
        try:
            _u32.SetForegroundWindow(self._hwnd)
        except OSError:
            pass
        w.focus_force()
        self._had_focus = False
        w.after(60, self._watch)
        w.after(500, self._refresh_status)

    def _switch(self, on, w, h):
        t = self.t

        def create():
            if on:
                img = tm.rounded_shape(w, h, h // 2, gradient=tm.GRADIENT)
            else:
                img = tm.rounded_shape(w, h, h // 2, t.c["border"])
            d = h - t.px(4)
            knob = tm.rounded_shape(d, d, d // 2, "#FFFFFF")
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            layer.paste(knob, (w - d - t.px(2) if on else t.px(2), t.px(2)))
            return Image.alpha_composite(img, layer)

        return t.photo(("switch", on, w, h, t.dark), create)

    def _update_status(self):
        text, kind = self._status()
        t = self.t
        color = tm.DOT.get(kind, tm.DOT["neutral"])
        d = t.px(8)
        self._dot.config(image=t.photo(("dot", color, d), lambda: tm.rounded_shape(d, d, d // 2, color)))
        self._status_label.config(text=text)

    def _refresh_status(self):
        if self.window is None:
            return
        self._update_status()
        self.window.after(500, self._refresh_status)

    def _position(self):
        w = self.window
        w.update_idletasks()
        width, height = w.winfo_reqwidth(), w.winfo_reqheight()
        mx, my = w.winfo_pointerxy()
        area = _work_area(mx, my) or (0, 0, w.winfo_screenwidth(), w.winfo_screenheight())
        left, top, right, bottom = area
        x = mx - width if mx - width >= left else mx
        x = max(left, min(x, right - width))
        y = min(my, bottom) - height
        if y < top:
            y = max(my, top)
        y = max(top, min(y, bottom - height))
        w.geometry(f"+{x}+{y}")

    def _round_corners(self):
        try:
            value = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(self._hwnd, 33, ctypes.byref(value), 4)
        except (AttributeError, OSError):
            pass

    def _click(self, event, item, cv, switch, sw_w, sw_h):
        if not (0 <= event.x <= cv.winfo_width() and 0 <= event.y <= cv.winfo_height()):
            return
        if item.is_on:
            item.action()
            cv.itemconfig(switch, image=self._switch(item.is_on(), sw_w, sw_h))
            return
        self.close()
        self.root.after(10, item.action)

    def _watch(self):
        w = self.window
        if w is None:
            return
        try:
            if _u32.GetForegroundWindow() == self._hwnd:
                self._had_focus = True
            elif self._had_focus:
                return self.close()
            if any(_u32.GetAsyncKeyState(b) & 0x8000 for b in (0x01, 0x02, 0x04)):
                mx, my = w.winfo_pointerxy()
                x0, y0 = w.winfo_rootx(), w.winfo_rooty()
                if not (x0 <= mx < x0 + w.winfo_width() and y0 <= my < y0 + w.winfo_height()):
                    return self.close()
        except tk.TclError:
            return
        w.after(60, self._watch)
