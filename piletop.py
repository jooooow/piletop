import argparse
import sys
import math
import psutil
import random
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Static
from rich.text import Text
from rich.style import Style

OLD_CONFIG_FILE = Path.home() / ".piletoprc"
XDG_CONFIG_DIR = Path.home() / ".config" / "piletop"
CONFIG_FILE = XDG_CONFIG_DIR / "config"

THEMES = {
    "classic": {
        "low": (0, 255, 0),
        "high": (255, 0, 0),
        "name": "Classic (Green -> Red)"
    },
    "cyberpunk": {
        "low": (0, 40, 150),
        "high": (255, 0, 128),
        "name": "Cyberpunk (Neon Blue -> Pink)"
    },
    "dracula": {
        "low": (95, 0, 135),
        "high": (255, 135, 0),
        "name": "Dracula (Purple -> Orange)"
    },
    "ice": {
        "low": (0, 50, 100),
        "high": (0, 255, 200),
        "name": "Ice (Deep Blue -> Cyan)"
    },
    "monochrome": {
        "low": (30, 30, 30),
        "high": (255, 255, 255),
        "name": "Monochrome (Dark -> White)"
    }
}

def load_saved_theme(fallback: str) -> str:
    targets = [CONFIG_FILE, OLD_CONFIG_FILE]
    for path in targets:
        if path.exists():
            try:
                content = path.read_text().strip()
                for line in content.splitlines():
                    if line.startswith("theme="):
                        theme_val = line.split("=", 1)[1].strip()
                        if theme_val in THEMES:
                            return theme_val
            except Exception:
                pass
    return fallback

def save_theme(theme_name: str) -> None:
    try:
        if not XDG_CONFIG_DIR.exists():
            XDG_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(f"theme={theme_name}\n")
        if OLD_CONFIG_FILE.exists():
            try:
                OLD_CONFIG_FILE.unlink()
            except Exception:
                pass
    except Exception:
        pass

def interpolate_color(low: tuple[int, int, int], high: tuple[int, int, int], factor: float) -> Style:
    r = int(low[0] + (high[0] - low[0]) * factor)
    g = int(low[1] + (high[1] - low[1]) * factor)
    b = int(low[2] + (high[2] - low[2]) * factor)
    return Style(bgcolor=f"rgb({r},{g},{b})")

def calculate_layout(core_count: int, terminal_w: int, terminal_h: int, char_aspect: float = 2.0) -> tuple[int, int, int, int] | None:
    if terminal_h < 3 or terminal_w < 6:
        return None

    best_cols = None
    best_rows = None
    best_score = (float('inf'), float('inf'))

    for cols in range(1, core_count + 1):
        rows = math.ceil(core_count / cols)
        empty_slots = (cols * rows) - core_count
        
        cell_w = terminal_w / cols
        cell_h = terminal_h / rows
        cell_h_equivalent_w = cell_h * char_aspect
        aspect_ratio = cell_w / cell_h_equivalent_w
        ratio_deviation = abs(aspect_ratio - 1.2)
        
        if cell_w >= 3 and cell_h >= 2: 
            current_score = (empty_slots, ratio_deviation)
            if best_score is None or current_score < best_score:
                best_score = current_score
                best_cols = cols
                best_rows = rows

    if best_cols is None or best_rows is None:
        return None

    total_cell_h = max(2, math.floor(terminal_h / best_rows))
    inner_char_h = max(1, total_cell_h - 1) 
    
    inner_char_w = max(2, round(inner_char_h * char_aspect))
    
    max_width = math.floor(terminal_w / best_cols) - 1
    max_width = max(2, max_width)
    if inner_char_w > max_width:
        inner_char_w = max_width

    if inner_char_w % 2 != 0 and inner_char_w > 2:
        inner_char_w = inner_char_w - 1

    if inner_char_w < 3 or inner_char_h < 1:
        return None

    return best_cols, best_rows, inner_char_w, inner_char_h


class PiletopApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "next_theme", "Switch Theme")
    ]
    CHAR_ASPECT = 2.0
    
    CSS = """
    Screen {
        background: black;
        overflow: hidden; 
        layout: vertical;
    }
    #main-display {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        overflow: hidden; 
    }
    #footer-display {
        width: 100%;
        height: 1;
        background: rgb(20,20,20);
        color: rgb(150,150,150);
        content-align: center middle;
        text-style: dim;
    }
    """

    def __init__(self, interval: float = 0.1, mock_cores: int | None = None, initial_theme: str = "classic", **kwargs):
        super().__init__(**kwargs)
        self.interval = interval
        self.mock_cores = mock_cores
        self.theme_keys = list(THEMES.keys())
        
        saved_theme = load_saved_theme(fallback=initial_theme)
        self.current_theme_index = self.theme_keys.index(saved_theme)

    def get_current_theme_colors(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        theme_cfg = THEMES[self.theme_keys[self.current_theme_index]]
        return theme_cfg["low"], theme_cfg["high"]

    def action_next_theme(self) -> None:
        self.current_theme_index = (self.current_theme_index + 1) % len(self.theme_keys)
        save_theme(self.theme_keys[self.current_theme_index])
        self.draw_heatmap()

    def compose(self) -> ComposeResult:
        if self.mock_cores is not None:
            self.core_count = self.mock_cores
        else:
            self.core_count = psutil.cpu_count(logical=True)
            
        self.current_usages = [0.0] * self.core_count
        yield Static(id="main-display")
        yield Static(id="footer-display")

    def on_mount(self) -> None:
        if self.mock_cores is None:
            psutil.cpu_percent(interval=None, percpu=True)
        self.set_interval(self.interval, self.refresh_data)

    def on_resize(self) -> None:
        self.draw_heatmap()

    def refresh_data(self) -> None:
        if self.mock_cores is not None:
            self.current_usages = [random.uniform(0.0, 100.0) for _ in range(self.core_count)]
        else:
            self.current_usages = psutil.cpu_percent(interval=None, percpu=True)
        self.draw_heatmap()

    def draw_heatmap(self) -> None:
        terminal_w = max(1, self.size.width)
        terminal_h_with_footer = max(1, self.size.height - 1)

        layout = calculate_layout(
            core_count=self.core_count,
            terminal_w=terminal_w,
            terminal_h=terminal_h_with_footer,
            char_aspect=self.CHAR_ASPECT
        )

        low_color, high_color = self.get_current_theme_colors()
        theme_name = THEMES[self.theme_keys[self.current_theme_index]]["name"]

        try:
            footer = self.query_one("#footer-display")
            footer.update(f"\[q] Quit | \[t] Theme: {theme_name}")
        except Exception:
            pass

        if layout is None:
            best_cols = None
            best_rows = None
            best_score = float('inf')
            
            for cols in range(1, self.core_count + 1):
                rows = math.ceil(self.core_count / cols)
                if cols <= terminal_w and rows <= terminal_h_with_footer:
                    empty_slots = (cols * rows) - self.core_count
                    if empty_slots < best_score:
                        best_score = empty_slots
                        best_cols = cols
                        best_rows = rows

            if best_cols is None or best_rows is None:
                total_text = Text(
                    "Terminal window is too small to render the heatmap.\n"
                    "Please resize or maximize the window.",
                    style="bold red",
                    justify="center"
                )
            else:
                cell_w = max(1, math.floor(terminal_w / best_cols))
                cell_h = max(1, math.floor(terminal_h_with_footer / best_rows))
                
                indexed_cores = list(range(self.core_count))
                rows_data = [indexed_cores[i:i + best_cols] for i in range(0, self.core_count, best_cols)]
                
                all_lines = []
                for row_cores in rows_data:
                    for h in range(cell_h):
                        line = Text()
                        for core_id in row_cores:
                            if core_id < len(self.current_usages):
                                core_usage = self.current_usages[core_id]
                            else:
                                core_usage = 0.0
                            style = interpolate_color(low_color, high_color, core_usage / 100.0)
                            line.append(" " * cell_w, style=style)
                        all_lines.append(line)
                
                total_text = Text("\n").join(all_lines)
        else:
            best_cols, best_rows, inner_char_w, inner_char_h = layout
            gap_style = Style(bgcolor="black")
            label_style = Style(color="white", bold=True)  
            
            indexed_cores = list(range(self.core_count))
            rows_data = [indexed_cores[i:i + best_cols] for i in range(0, self.core_count, best_cols)]
            
            all_lines = []
            
            for r_idx, row_cores in enumerate(rows_data):
                label_line = Text()
                color_lines = [Text() for _ in range(inner_char_h)]
                
                for core_id in row_cores:
                    if core_id < len(self.current_usages):
                        core_usage = self.current_usages[core_id]
                    else:
                        core_usage = 0.0
                    style = interpolate_color(low_color, high_color, core_usage / 100.0)
                    
                    label = f"{core_id}"
                    label_len = len(label)
                    if inner_char_w >= label_len:
                        remaining = inner_char_w - label_len
                        left = remaining // 2
                        right = remaining - left
                        label_line.append(" " * left + label + " " * right, style=label_style)
                    else:
                        label_line.append(label[:inner_char_w], style=label_style)
                    label_line.append(" ", style=gap_style)
                    
                    for h in range(inner_char_h):
                        color_lines[h].append(" " * inner_char_w, style=style)
                        color_lines[h].append(" ", style=gap_style)
                
                all_lines.append(label_line)
                all_lines.extend(color_lines)
                
            total_text = Text("\n").join(all_lines)
                
        try:
            display = self.query_one("#main-display", Static)
            display.update(total_text)
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(
        description="A real-time CPU heatmap terminal visualizer"
    )
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=0.5,
        help="Refresh interval in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--cores",
        type=int,
        default=None,
        help="Simulate a custom number of cores for debugging"
    )
    parser.add_argument(
        "-t", "--theme",
        type=str,
        choices=list(THEMES.keys()),
        default="classic",
        help="Initial color theme (default: classic)"
    )
    args = parser.parse_args()

    if args.interval <= 0:
        print("Error: Refresh interval must be greater than 0.", file=sys.stderr)
        sys.exit(1)

    if args.cores is not None and args.cores <= 0:
        print("Error: Custom core count must be greater than 0.", file=sys.stderr)
        sys.exit(1)

    app = PiletopApp(interval=args.interval, mock_cores=args.cores, initial_theme=args.theme)
    app.run()

if __name__ == "__main__":
    main()