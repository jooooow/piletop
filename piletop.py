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
            
            if cell_w >= 6 and cell_h >= 3: 
                if score < best_score:
                    best_score = score
                    best_cols = cols
                    best_rows = rows

        max_cell_char_w = math.floor(terminal_w / best_cols) - 2 
        max_cell_char_h = math.floor(terminal_h / best_rows) - 1 

        max_cell_char_w = max(6, max_cell_char_w)
        max_cell_char_h = max(3, max_cell_char_h)

        inner_char_h = max(1, max_cell_char_h - 2) 
        inner_char_w = max(2, round(inner_char_h * self.CHAR_ASPECT))
        
        if inner_char_w + 2 > max_cell_char_w:
            inner_char_w = max_cell_char_w - 2

        if inner_char_w % 2 != 0:
            inner_char_w = max(2, inner_char_w - 1)

        number_row_idx = 1 + (inner_char_h - 1) // 2

        border_style = Style(color="rgb(80,80,80)")
        num_style = Style(color="white", bold=True)
        total_text = Text()
        
        indexed_cores = list(range(self.core_count))
        rows_data = [indexed_cores[i:i + best_cols] for i in range(0, self.core_count, best_cols)]
        
        for r_idx, row_cores in enumerate(rows_data):
            lines = [Text() for _ in range(inner_char_h + 2)]
            
            for core_id in row_cores:
                core_usage = self.current_usages[core_id]
                style = get_heatmap_style(core_usage)
                
                lines[0].append("┌" + "─" * inner_char_w + "┐", style=border_style)
                lines[0].append("  ")
                
                for h in range(1, inner_char_h + 1):
                    lines[h].append("│", style=border_style)
                    
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
                        
                    lines[h].append("│", style=border_style)
                    lines[h].append("  ")
                
                lines[-1].append("└" + "─" * inner_char_w + "┘", style=border_style)
                lines[-1].append("  ")
            
            for line in lines:
                total_text.append(line).append("\n")
                
            if r_idx < len(rows_data) - 1:
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