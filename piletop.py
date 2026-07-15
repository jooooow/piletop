import argparse
import sys
import math
import psutil
from textual.app import App, ComposeResult
from textual.widgets import Static
from rich.text import Text
from rich.style import Style

def get_heatmap_style(usage_percent: float) -> Style:
    factor = usage_percent / 100.0
    r = int(255 * factor)
    g = int(255 * (1.0 - factor))
    b = 0
    return Style(bgcolor=f"rgb({r},{g},{b})")

def calculate_layout(core_count: int, terminal_w: int, terminal_h: int, char_aspect: float = 2.0) -> tuple[int, int, int, int] | None:
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
        
        if cell_w >= 4 and cell_h >= 2: 
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

    if inner_char_w < 4 or inner_char_h < 1:
        return None

    return best_cols, best_rows, inner_char_w, inner_char_h


class PiletopApp(App):
    BINDINGS = [("q", "quit", "Quit")]
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

    def __init__(self, interval: float = 0.1, **kwargs):
        super().__init__(**kwargs)
        self.interval = interval

    def compose(self) -> ComposeResult:
        self.core_count = psutil.cpu_count(logical=True)
        self.current_usages = [0.0] * self.core_count
        yield Static(id="main-display")
        yield Static(
            "\[q] Quit | Red (High CPU) -> Green (Low CPU)", 
            id="footer-display"
        )

    def on_mount(self) -> None:
        psutil.cpu_percent(interval=None, percpu=True)
        self.set_interval(self.interval, self.refresh_data)

    def on_resize(self) -> None:
        self.draw_heatmap()

    def refresh_data(self) -> None:
        self.current_usages = psutil.cpu_percent(interval=None, percpu=True)
        self.draw_heatmap()

    def draw_heatmap(self) -> None:
        terminal_w = max(10, self.size.width)
        terminal_h = max(6, self.size.height - 1)

        layout = calculate_layout(
            core_count=self.core_count,
            terminal_w=terminal_w,
            terminal_h=terminal_h,
            char_aspect=self.CHAR_ASPECT
        )

        if layout is None:
            total_text = Text(
                "Terminal window is too small to render the heatmap.\n"
                "Please resize or maximize the window.",
                style="bold red",
                justify="center"
            )
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
                    core_usage = self.current_usages[core_id]
                    style = get_heatmap_style(core_usage)
                    
                    label = f"#{core_id}"
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
        default=0.1,
        help="Refresh interval in seconds (default: 0.1)"
    )
    args = parser.parse_args()

    if args.interval <= 0:
        print("Error: Refresh interval must be greater than 0.", file=sys.stderr)
        sys.exit(1)

    app = PiletopApp(interval=args.interval)
    app.run()

if __name__ == "__main__":
    main()