import psutil
from textual.app import App, ComposeResult
from textual.widgets import Static
from rich.text import Text
from rich.style import Style
import math

def get_heatmap_style(usage_percent: float) -> Style:
    factor = usage_percent / 100.0
    r = int(255 * factor)
    g = int(255 * (1.0 - factor))
    b = 0
    return Style(color=f"rgb({r},{g},{b})")

class PiletopApp(App):
    BINDINGS = [("q", "quit", "Quit")]
    CHAR_ASPECT = 2.0
    
    CSS = """
    Screen {
        background: black;
    }
    #main-display {
        width: 100%;
        height: 100%;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        self.core_count = psutil.cpu_count(logical=True)
        self.current_usages = [0.0] * self.core_count
        yield Static(id="main-display")

    def on_mount(self) -> None:
        psutil.cpu_percent(interval=None, percpu=True)
        self.set_interval(0.5, self.refresh_data)

    def on_resize(self) -> None:
        self.draw_heatmap()

    def refresh_data(self) -> None:
        self.current_usages = psutil.cpu_percent(interval=None, percpu=True)
        self.draw_heatmap()

    def draw_heatmap(self) -> None:
        terminal_w = max(10, self.size.width - 4)
        terminal_h = max(6, self.size.height - 2)

        best_cols = 1
        best_rows = self.core_count
        best_score = float('inf')

        for cols in range(1, self.core_count + 1):
            rows = math.ceil(self.core_count / cols)
            cell_w = terminal_w / cols
            cell_h = terminal_h / rows
            cell_h_equivalent_w = cell_h * self.CHAR_ASPECT
            aspect_ratio = cell_w / cell_h_equivalent_w
            score = abs(aspect_ratio - 1.2)
            
            if cell_w >= 4 and cell_h >= 1: 
                if score < best_score:
                    best_score = score
                    best_cols = cols
                    best_rows = rows

        inner_char_h = max(1, math.floor(terminal_h / best_rows) - 1)
        inner_char_h = max(1, inner_char_h)
        inner_char_w = max(2, round(inner_char_h * self.CHAR_ASPECT))
        
        max_width = math.floor(terminal_w / best_cols) - 1
        max_width = max(2, max_width)
        if inner_char_w > max_width:
            inner_char_w = max_width

        if inner_char_w % 2 != 0 and inner_char_w > 2:
            inner_char_w = inner_char_w - 1

        number_row_idx = (inner_char_h - 1) // 2

        num_style = Style(color="white", bold=True)
        gap_style = Style(bgcolor="black")
        total_text = Text()
        
        indexed_cores = list(range(self.core_count))
        rows_data = [indexed_cores[i:i + best_cols] for i in range(0, self.core_count, best_cols)]
        
        for r_idx, row_cores in enumerate(rows_data):
            lines = [Text() for _ in range(inner_char_h)]
            
            for core_id in row_cores:
                core_usage = self.current_usages[core_id]
                style = get_heatmap_style(core_usage)
                
                for h in range(inner_char_h):
                    if h == number_row_idx:
                        label = f"{core_id}"
                        label_len = len(label)
                        
                        if inner_char_w < label_len:
                            lines[h].append("█" * inner_char_w, style=style)
                        else:
                            remaining_space = inner_char_w - label_len
                            left_spaces = remaining_space // 2
                            right_spaces = remaining_space - left_spaces
                            
                            lines[h].append("█" * left_spaces, style=style)
                            lines[h].append(label, style=num_style + Style(bgcolor=style.color))
                            lines[h].append("█" * right_spaces, style=style)
                    else:
                        lines[h].append("█" * inner_char_w, style=style)
                    
                    lines[h].append(" ", style=gap_style)
            
            for line in lines:
                total_text.append(line).append("\n")
            
            total_text.append("\n")
                
        try:
            display = self.query_one("#main-display", Static)
            display.update(total_text)
        except Exception:
            pass

def main():
    app = PiletopApp()
    app.run()

if __name__ == "__main__":
    main()