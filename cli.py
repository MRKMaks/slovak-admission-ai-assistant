"""
cli.py — Interactive CLI client for AI Form Filler.

    python cli.py start
    python cli.py start --url http://localhost:8000
 """

from __future__ import annotations

import io
import sys

# Force UTF-8 on Windows terminals with cp1252
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text
from rich.theme import Theme


# Rich theme setup

_THEME = Theme(
    {
        "user": "bold cyan",
        "ai": "bold green",
        "system": "dim yellow",
        "error": "bold red",
        "success": "bold magenta",
        "status": "dim white",
    }
)

console = Console(theme=_THEME)
app = typer.Typer(
    name="form-filler",
    help="AI assistant for filling out the Slovak application form.",
    add_completion=False,
)

DEFAULT_API_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"



# API Client

class FormFillerClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/") + API_PREFIX
        self._http = httpx.Client(timeout=60.0)

    def create_session(self, template_filename: str | None = None) -> dict:
        params = {}
        if template_filename:
            params["template_filename"] = template_filename
        resp = self._http.post(f"{self._base}/sessions/", params=params)
        resp.raise_for_status()
        return resp.json()

    def send_message(self, session_id: str, content: str) -> dict:
        resp = self._http.post(
            f"{self._base}/sessions/{session_id}/messages",
            json={"content": content},
        )
        resp.raise_for_status()
        return resp.json()

    def export_pdf(self, session_id: str, out_path: Path, force: bool = False) -> Path:
        params = {"force": "true"} if force else {}
        with self._http.stream(
            "GET", f"{self._base}/sessions/{session_id}/export", params=params
        ) as resp:
            resp.raise_for_status()
            out_path.write_bytes(resp.read())
        return out_path

    def close(self) -> None:
        self._http.close()



# Start command

@app.command()
def start(
    url: str = typer.Option(
        DEFAULT_API_URL,
        "--url",
        "-u",
        help="Base URL of the FastAPI server",
        envvar="FORM_FILLER_URL",
    ),
    template: str = typer.Option(
        "formular.docx",
        "--template",
        "-t",
        help="Template file name",
    ),
    output: Path = typer.Option(
        Path("."),
        "--output",
        "-o",
        help="Directory to save PDF",
    ),
    session_id: str = typer.Option(
        None,
        "--session-id",
        "-s",
        help="ID of existing session to continue",
    ),
) -> None:
    console.print(Rule("[bold]AI Form Filler — Prihláška na VŠ[/bold]", style="magenta"))
    console.print(
        Panel(
            "[system]Connecting to server...[/system]",
            border_style="yellow",
        )
    )

    client = FormFillerClient(base_url=url)

    try:
        ping = httpx.get(f"{url}{API_PREFIX}/health", timeout=5.0)
        ping.raise_for_status()
        console.print("[system]Server is available.[/system]")
    except Exception as exc:
        console.print(f"[error]Server is unavailable: {exc}[/error]")
        console.print(
            f"[system]Start the server with the command: uvicorn app.main:app --reload[/system]"
        )
        raise typer.Exit(code=1)

    # Creating or restoring session
    form_data = {}
    try:
        if session_id:
            session_info = client._http.get(f"{client._base}/sessions/{session_id}")
            session_info.raise_for_status()
            session_data = session_info.json()
            form_data = session_data.get("form_data", {})
            console.print(
                Panel(
                    f"[status]Session restored: [bold]{session_id}[/bold][/status]",
                    border_style="dim",
                )
            )
        else:
            session_data = client.create_session(template_filename=template)
            session_id = session_data["session_id"]
            console.print(
                Panel(
                    f"[status]Session created: [bold]{session_id}[/bold][/status]",
                    border_style="dim",
                )
            )
    except Exception as exc:
        console.print(f"[error]Session error: {exc}[/error]")
        raise typer.Exit(code=1)

    console.print()

    is_restored = bool(session_id)
    current_status = "in_progress"
    is_forced = False

    # Welcome message
    if is_restored:
        console.print("[system]Restoring context...[/system]")
        try:
            resp = client.send_message(
                session_id=session_id,
                content="Pokračujeme v prihláške. Oslov ma menom (ak ho už vieš) a zhrň, aké údaje ešte chýbajú k dokončeniu."
            )
            form_data = resp.get("form_data", form_data)
            _print_ai_message(resp["reply"])
            current_status = resp["status"]
        except Exception as exc:
            console.print(f"[error]Error restoring dialog: {exc}[/error]")
            raise typer.Exit(code=1)
    else:
        _print_ai_message(
            "Dobrý deň! Som váš AI asistent na vyplnenie prihlášky na vysokoškolské štúdium. "
            "Budem vám klásť otázky postupne. Začnime!"
        )

    
    # Main dialog loop
    

    while current_status != "completed":
        # Reading user input
        try:
            user_input = _prompt_user()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[system]Dialog interrupted by user.[/system]")
            client.close()
            raise typer.Exit(code=0)

        if not user_input.strip():
            console.print("[system]Enter text and press Enter.[/system]")
            continue

        # Sending message
        try:
            response = client.send_message(session_id=session_id, content=user_input)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                console.print("[error]Session not found. Try restarting the client.[/error]")
                raise typer.Exit(code=1)
            console.print(f"[error]API Error ({exc.response.status_code}): {exc.response.text}[/error]")
            continue
        except Exception as exc:
            console.print(f"[error]Connection error: {exc}[/error]")
            continue

        current_status = response.get("status", "in_progress")
        ai_reply: str = response.get("reply", "")
        form_data = response.get("form_data", form_data)

        _PDF_TRIGGERS = {
            "pdf prihlášku vytvorí",
            "pdf prihlasku vytvorí",
            "pdf prihlasku vytvorit",
            "daj pdf",
            "daj mi pdf",
            "vytvor pdf",
            "generuj pdf",
            "dakujem",
            "ďakujem",
        }
        user_lower = user_input.lower().strip()
        is_forced = False
        if any(trigger in user_lower for trigger in _PDF_TRIGGERS):
            current_status = "completed"
            is_forced = True

        _print_ai_message(ai_reply)

        if current_status == "completed":
            break

    
    # Downloading PDF
    

    console.print()
    console.print(Rule("[success]Form filled![/success]", style="magenta"))
    console.print(
        Panel(
            "[success]All mandatory fields collected. Generating PDF...[/success]",
            border_style="green",
        )
    )

    import datetime
    now_str = datetime.datetime.now().strftime("%d_%m_%Y-%H-%M-%S")
    pi = form_data.get("personal_info") or {}
    meno = pi.get("first_name") or "nezname"
    pdf_filename = output / f"prihlaska-{meno}-{now_str}.pdf"
    try:
        saved_path = client.export_pdf(session_id=session_id, out_path=pdf_filename, force=is_forced)
        console.print(
            Panel(
                f"[success]PDF saved:[/success] [bold cyan]{saved_path.resolve()}[/bold cyan]",
                border_style="green",
                title="Done",
            )
        )
    except httpx.HTTPStatusError as exc:
        console.print(f"[error]Export error ({exc.response.status_code}): {exc.response.text}[/error]")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[error]Error saving PDF: {exc}[/error]")
        raise typer.Exit(code=1)
    finally:
        client.close()

    console.print()
    console.print(
        "[system]Thank you for using AI Form Filler. Good luck with your admission![/system]"
    )



# Helper display functions

def _print_ai_message(text: str) -> None:
    console.print(
        Panel(
            Text(text, style="ai"),
            title="[ai]AI Asistent[/ai]",
            border_style="green",
            padding=(0, 1),
        )
    )
    console.print()


def _prompt_user() -> str:
    return Prompt.ask("[user]Vy[/user]")



# Entry point
if __name__ == "__main__":
    app()
