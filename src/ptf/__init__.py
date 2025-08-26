import contextlib
from asyncio import sleep
from pathlib import Path

import click
import fitz
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup, VerticalGroup
from textual.widgets import Button, Footer, Input, Label
from textual_pdf.pdf_viewer import NotAPDFError, PDFViewer


class PDFTestApp(App):
    """A simple app to test the PDFViewer."""

    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("left", "key_event('prev')", "Previous Page"),
        ("right", "key_event('next')", "Next Page"),
        ("ctrl+q", "quit", "Quit"),
    ]

    ENABLE_COMMAND_PALETTE = False

    def __init__(self, pdf_path: str | Path, render_with: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pdf_path = pdf_path if isinstance(pdf_path, Path) else Path(pdf_path)
        self.render_with = render_with

    def compose(self) -> ComposeResult:
        with VerticalGroup():
            yield PDFViewer(self.pdf_path, protocol=self.render_with)
            with HorizontalGroup(id="outer"):
                yield Label(id="empty_focusable")
                yield Button("<", id="prev")
                with HorizontalGroup(id="inner"):
                    yield Input("1", id="current", compact=True)
                    yield Label("/ ")
                    yield Label("0", id="total")
                yield Button(">", id="next")
        yield Footer()

    def on_mount(self) -> None:
        self.pdf_viewer: PDFViewer = self.query_one(PDFViewer)
        self.pdf_viewer.can_focus = False
        self.query_one("#empty_focusable").can_focus = True
        self.focus_nothing()
        self.query_one("#total").update(str(self.pdf_viewer.total_pages))
        self.fix_buttons()
        self.start_watching_please()

    @work
    async def start_watching_please(self) -> None:
        prev_stmtime = self.pdf_path.stat().st_mtime
        while True:
            await sleep(1)
            new_stmtime = self.pdf_path.stat().st_mtime
            if new_stmtime != prev_stmtime:
                with contextlib.suppress(NotAPDFError):
                    current_page = self.pdf_viewer.current_page
                    self.pdf_viewer.doc = fitz.open(self.pdf_path)
                    self.pdf_viewer._cache = {}
                    if self.pdf_viewer.total_pages <= current_page:
                        self.pdf_viewer.current_page = self.pdf_viewer.total_pages - 1
                    else:
                        self.pdf_viewer.current_page -= 1
                        self.pdf_viewer.current_page += 1
                    self.fix_buttons()
            prev_stmtime = new_stmtime

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prev":
            self.pdf_viewer.previous_page()
        elif event.button.id == "next":
            self.pdf_viewer.next_page()
        self.fix_buttons()

    def focus_nothing(self) -> None:
        self.query_one("#empty_focusable").focus()

    def fix_buttons(self) -> None:
        with self.batch_update():
            self.query_one("#prev").disabled = self.pdf_viewer.current_page == 0
            self.query_one("#next").disabled = (
                self.pdf_viewer.total_pages - 1 == self.pdf_viewer.current_page
            )
            self.query_one("#current").value = str(self.pdf_viewer.current_page + 1)
            total: Label = self.query_one("#total")
            if total.visual != self.pdf_viewer.total_pages:
                total.update(str(self.pdf_viewer.total_pages))

    def on_input_changed(self, event: Input.Changed) -> None:
        event.input.styles.max_width = len(event.value) + 2
        event.input.parent.styles.width = len(event.value) + len(str(self.pdf_viewer.total_pages)) + 7
        if (
            event.value.isnumeric()
            and self.pdf_viewer.current_page != int(event.value)
            and int(event.value) < self.pdf_viewer.total_pages
        ):
            self.pdf_viewer.current_page = int(event.value) - 1

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.focus_nothing()

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        if self.focused.id == "current" and event.key not in ["up", "down"]:
            if event.key == "escape":
                self.focus_nothing()
            return
        match event.key:
            case "down" | "page_down" | "right" | "j" | "l":
                event.stop()
                self.pdf_viewer.next_page()
                self.fix_buttons()
            case "up" | "page_up" | "left" | "k" | "h":
                event.stop()
                self.pdf_viewer.previous_page()
                self.fix_buttons()
            case "home" | "g":
                event.stop()
                self.pdf_viewer.go_to_start()
                self.fix_buttons()
            case "end" | "G":
                event.stop()
                self.pdf_viewer.go_to_end()
                self.fix_buttons()
            case "i":
                event.stop()
                self.query_one(Input).focus()


@click.command(help="test appplication for textual-pdf-view")
@click.argument("filename")
def main(filename: str) -> None:
    """Run the PDF test app."""
    app = PDFTestApp(filename, render_with="Auto", ansi_color=True, watch_css=True)
    app.run()
