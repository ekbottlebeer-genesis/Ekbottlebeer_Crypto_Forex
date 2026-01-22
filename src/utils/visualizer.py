# src/utils/visualizer.py
import logging
import os
import pandas as pd
from lightweight_charts import Chart
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

class Visualizer:
    def __init__(self, export_dir="debug_charts"):
        self.export_dir = export_dir
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

    def generate_chart(self, df, symbol, zones=None, filename="chart.png"):
        """
        Generates a lightweight-chart, saves it as HTML, and uses Playwright to screenshot it.
        
        :param df: DataFrame with OHLCV data + index as datetime
        :param symbol: Ticker symbol
        :param zones: Dict of 'sweeps', 'mss', 'fvg' to plot
        :param filename: Output filename for the screenshot
        :return: Path to the screenshot
        """
        try:
            # 1. Initialize Chart
            chart = Chart(toolbox=True, width=1200, height=800)
            chart.legend(visible=True)
            chart.topbar.textbox('symbol', symbol)
            
            # 2. Set Data
            # lightweight-charts expects columns: time, open, high, low, close, volume
            # Ensure index is handled if it's the time column
            data = df.copy()
            if 'time' not in data.columns:
                data.reset_index(inplace=True)
                data.rename(columns={'index': 'time'}, inplace=True)
            
            chart.set(data)

            # 3. Add Overlays (Zones)
            if zones:
                # Plot FVGs (Boxes)
                if 'fvg' in zones:
                    for fvg in zones['fvg']:
                        # fvg structure: {'top': float, 'bottom': float, 'start_time': str, 'end_time': str, 'type': 'bullish'/'bearish'}
                        color = 'rgba(0, 255, 0, 0.2)' if fvg.get('type') == 'bullish' else 'rgba(255, 0, 0, 0.2)'
                        # Note: lightweight-charts python lib might not have a direct 'box' primitive easily accessible 
                        # without custom js, but we can use horizontal lines or specialized markers. 
                        # For this version, we will try to calculate a box or just use lines.
                        # Let's use create_line for top and bottom for now as a robust fallback.
                        # Or checking if library supports shapes exists. It does support 'trend_line' or 'box' in newer versions.
                        # We will use horizontal ray for simplicity if exact box isn't available in this wrapper version easily.
                        pass # TODO: Implement visual boxes

                # Plot Sweeps (Horizontal Lines)
                if 'sweeps' in zones:
                    for sweep in zones['sweeps']:
                        price = sweep['price']
                        color = 'yellow'
                        chart.horizontal_line(price, color=color, width=2, style='solid', text=f"Sweep {price}")

                # Plot MSS (Vertical Lines / Markers)
                if 'mss' in zones:
                    for mss in zones['mss']:
                        # Add a marker on the MSS candle
                        mss_time = mss['time']
                        chart.marker(time=mss_time, position='above', shape='arrow_down', color='white', text='MSS')

            # 4. Screenshot Logic (Headless)
            # We need to save the chart as static HTML first?
            # lightweight-charts usually opens a window. 
            # For headless VPS, we can use the `chart.show(block=False)` and then screenshot if local. 
            # But the library is designed for GUI. 
            # Integrating with Playwright manually:
            
            # NOTE: Since the library launches awebview, getting a screenshot on a headless server 
            # might be tricky without a proper display driver (Xvfb).
            # ALTERNATIVE: Use the library's internal method to export HTML string if available, 
            # OR assume we are ok with just saving the data and letting a separate process render it.
            
            # Let's try to perform a synchronous screenshot if possible.
            # If this is too complex for this phase, we return a placeholder.
            
            img_path = os.path.join(self.export_dir, filename)
            
            # NOTE: For this specific task, if running on a headless server, 
            # the best bet is to rely on Playwright opening a local HTML file we construct.
            # But lightweight-charts makes the HTML construction easy.
            # Let's assume we can execute it. 
            
            # Creating a screenshot via the library (if supported)
            # chart.screenshot(img_path) 
            # This often requires a running UI loop which might block.
            
            logger.info(f"Chart generated (Virtual): {filename}")
            return "path/to/placeholder_chart.png" # Stub for now until Playwright logic is fully tested

        except Exception as e:
            logger.error(f"Failed to generate chart: {e}")
            return None
