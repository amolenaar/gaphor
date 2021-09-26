#!/usr/bin/env python

#  GTK Interactive Console
#  (C) 2003, Jon Anderson
#  See www.python.org/2.2/license.html for
#  license details.
#

import code
import sys
import textwrap
from rlcompleter import Completer
from typing import Dict, List

from gi.repository import Gdk, Gtk, Pango

from gaphor.i18n import gettext

banner = gettext(
    """\
Gaphor Interactive Python Console
{version}
Type "help" for more information.
"""
).format(version=sys.version)


def docstring_dedent(docstr: str) -> str:
    if docstr.startswith(" "):
        return textwrap.dedent(docstr)

    first_line, remaining_text = docstr.split("\n", 1)

    return "\n".join([first_line, textwrap.dedent(remaining_text)])


class Help:
    def __init__(self, writer, locals={}):
        self._writer = writer
        self._locals = locals

    def __call__(self, obj=None):
        helptext = docstring_dedent(obj.__doc__ if obj else str(self))
        with self._writer as writer:
            writer.write("\n")
            writer.write(textwrap.indent(helptext, prefix="  "))
            writer.write("\n" if helptext.endswith("\n") else "\n\n")

    def __str__(self):
        intro = textwrap.dedent(
            """\

        Usage: help(object)

        The following functions/variables are defined:
        """
        )

        members = "\n".join(
            f"- {key}" for key in self._locals.keys() if not key.startswith("_")
        )

        return textwrap.indent(intro + members + "\n", prefix="  ")

    def __repr__(self):
        return str(self)


class TextViewWriter:
    """A Multiplexing output stream.

    It can replace another stream, and tee output to the original stream
    and too a GTK textview.
    """

    def __init__(self, name, view, style):
        self.name = name
        self.out = getattr(sys, name)
        self.view = view
        self.style = style

    def write(self, text):
        buffer = self.view.get_buffer()
        end = buffer.get_end_iter()
        buffer.insert_with_tags(end, text, self.style)

    def __enter__(self):
        setattr(sys, self.name, self)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        setattr(sys, self.name, self.out)


class GTKInterpreterConsole(Gtk.ScrolledWindow):
    """An InteractiveConsole for GTK.

    It's an actual widget, so it can be dropped in just about anywhere.
    """

    __gtype_name__ = "GTKInterpreterConsole"

    def __init__(self, locals: Dict[str, object], banner=banner):
        Gtk.ScrolledWindow.__init__(self)
        self.locals = dict(locals)

        self.set_min_content_width(640)
        self.set_min_content_height(480)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.text = Gtk.TextView()
        self.text.set_wrap_mode(True)
        self.text.set_monospace(True)

        self.interpreter = code.InteractiveInterpreter(locals)

        self.completer = Completer(locals)
        self.buffer: List[str] = []
        self.history: List[str] = []
        self.banner = banner
        self.ps1 = ">>> "
        self.ps2 = "... "

        if Gtk.get_major_version() == 3:
            self.text_controller = Gtk.EventControllerKey.new(self.text)
        else:
            self.text_controller = Gtk.EventControllerKey.new()
            self.text.add_controller(self.text_controller)

        self.text_controller.connect("key-pressed", self.key_pressed)

        self.current_history = -1

        self.mark = self.text.get_buffer().create_mark(
            "End", self.text.get_buffer().get_end_iter(), False
        )

        # setup colors
        self.style_banner = Gtk.TextTag.new("banner")
        self.style_banner.set_property("foreground", "saddle brown")

        self.style_ps1 = Gtk.TextTag.new("ps1")
        self.style_ps1.set_property("foreground", "DarkOrchid4")
        self.style_ps1.set_property("editable", False)

        self.style_ps2 = Gtk.TextTag.new("ps2")
        self.style_ps2.set_property("foreground", "DarkOliveGreen")
        self.style_ps2.set_property("editable", False)

        self.style_out = Gtk.TextTag.new("stdout")
        self.style_out.set_property("foreground", "midnight blue")
        self.style_out.set_property("editable", False)
        self.style_err = Gtk.TextTag.new("stderr")
        self.style_err.set_property("style", Pango.Style.ITALIC)
        self.style_err.set_property("foreground", "red")
        self.style_err.set_property("editable", False)

        self.text.get_buffer().get_tag_table().add(self.style_banner)
        self.text.get_buffer().get_tag_table().add(self.style_ps1)
        self.text.get_buffer().get_tag_table().add(self.style_ps2)
        self.text.get_buffer().get_tag_table().add(self.style_out)
        self.text.get_buffer().get_tag_table().add(self.style_err)

        self.stdout = TextViewWriter("stdout", self.text, self.style_out)
        self.stderr = TextViewWriter("stderr", self.text, self.style_err)

        self.current_prompt = lambda: ""
        locals["help"] = Help(self.stdout, locals)

        if Gtk.get_major_version() == 3:
            self.add(self.text)
        else:
            self.set_child(self.text)
        self.text.show()

        self.write_line(self.banner, self.style_banner)
        self.prompt_ps1()

    def reset_history(self):
        self.history = []

    def reset_buffer(self):
        self.buffer = []

    def prompt_ps1(self):
        self.current_prompt = self.prompt_ps1
        self.write_line(self.ps1, self.style_ps1)

    def prompt_ps2(self):
        self.current_prompt = self.prompt_ps2
        self.write_line(self.ps2, self.style_ps2)

    def write_line(self, text, style=None):
        start, end = self.text.get_buffer().get_bounds()
        if style:
            self.text.get_buffer().insert_with_tags(end, text, style)
        else:
            self.text.get_buffer().insert(end, text)

        self.text.scroll_to_mark(self.mark, 0, True, 1, 1)

    def push(self, line):
        self.buffer.append(line)
        if len(line) > 0:
            self.history.append(line)

        source = "\n".join(self.buffer)

        with self.stdout, self.stderr:
            more = self.interpreter.runsource(source, "<<console>>")

        if not more:
            self.reset_buffer()

        return more

    def key_pressed(self, widget, keyval, keycode, state):
        if keyval == Gdk.keyval_from_name("Return"):
            return self.execute_line()
        if keyval == Gdk.keyval_from_name("Tab"):
            return self.complete_line()

        if keyval == Gdk.keyval_from_name("Up"):
            self.current_history = self.current_history - 1
            self.current_history = max(self.current_history, -len(self.history))
            return self.show_history()
        if keyval == Gdk.keyval_from_name("Down"):
            self.current_history = self.current_history + 1
            self.current_history = min(self.current_history, 0)
            return self.show_history()

        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        if (keyval == Gdk.keyval_from_name("Home")) or (ctrl and keyval == Gdk.KEY_a):
            line_count = self.text.get_buffer().get_line_count() - 1
            start = self.text.get_buffer().get_iter_at_line_offset(line_count, 4)
            self.text.get_buffer().place_cursor(start)
            return True

        if ctrl and keyval == Gdk.KEY_e:
            end = self.text.get_buffer().get_end_iter()
            self.text.get_buffer().place_cursor(end)
            return True

        return False

    def show_history(self):
        if self.current_history != 0:
            self.replace_line(self.history[self.current_history])

        return True

    def current_line(self):
        start, end = self.current_line_bounds()
        return self.text.get_buffer().get_text(start, end, True)

    def current_line_bounds(self):
        txt_buffer = self.text.get_buffer()
        line_count = txt_buffer.get_line_count() - 1

        if Gtk.get_major_version() == 3:
            start = txt_buffer.get_iter_at_line(line_count)
        else:
            _, start = txt_buffer.get_iter_at_line(line_count)
        if start.get_chars_in_line() >= 4:
            start.forward_chars(4)
        end = txt_buffer.get_end_iter()
        return start, end

    def replace_line(self, txt):
        start, end = self.current_line_bounds()
        self.text.get_buffer().delete(start, end)
        self.write_line(txt)

    def execute_line(self):
        line = self.current_line()

        self.write_line("\n")

        more = self.push(line)

        self.text.get_buffer().place_cursor(self.text.get_buffer().get_end_iter())

        if more:
            self.prompt_ps2()
        else:
            self.prompt_ps1()

        self.current_history = 0

        return True

    def complete_line(self):
        line = self.current_line()
        tokens = line.split()

        if tokens:
            token = tokens[-1]
            completions: List[str] = []
            p = self.completer.complete(token, len(completions))
            while p:
                assert p
                completions.append(p)
                p = self.completer.complete(token, len(completions))
        else:
            completions = list(self.locals.keys())

        if len(completions) > 1:
            max_len = max(map(len, completions)) + 2
            per_line = 80 // max_len
            for i, c in enumerate(completions):
                if i % per_line == 0:
                    self.write_line("\n")
                self.write_line(c, self.style_ps1)
                self.write_line(" " * (max_len - len(c)), self.style_ps1)
            self.write_line("\n")
            self.current_prompt()
            self.write_line(line)
        elif len(completions) == 1:
            i = line.rfind(token)
            line = line[0:i] + completions[0]
            self.replace_line(line)

        return True


def main(main_loop=True):
    w = Gtk.ApplicationWindow()
    console = GTKInterpreterConsole(locals())
    if Gtk.get_major_version() == 3:
        w.add(console)
    else:
        w.set_child(console)

    def destroy(arg=None):
        Gtk.main_quit()

    def key_event(widget, keyval, keycode, state):
        if keyval == Gdk.KEY_d and state & Gdk.ModifierType.CONTROL_MASK:
            destroy()
        return False

    w.connect("destroy", destroy)

    console.text_controller.connect("key-pressed", key_event)
    if Gtk.get_major_version() == 3:
        w.show_all()
    else:
        w.show()

    if main_loop:

        def on_startup(app):
            app.add_window(w)

        app = Gtk.Application.new("org.gaphor.Console", 0)
        app.connect("startup", on_startup)
        app.run()


if __name__ == "__main__":
    main()
