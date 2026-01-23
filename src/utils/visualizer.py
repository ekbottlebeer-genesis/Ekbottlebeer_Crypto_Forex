import logging
import os
import pandas as pd
import mplfinance as mpf

logger = logging.getLogger(__name__)

class Visualizer:
    def __init__(self, export_dir="debug_charts"):
        self.export_dir = export_dir
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

    def generate_chart(self, df, symbol, zones=None, filename="chart.png"):
        """
        Generates a static chart using mplfinance and saves it as an image.
        """
        try:
            if df is None or df.empty:
                logger.warning(f"Visualizer: No data for {symbol}")
                return None

            # Prepare Data (mplfinance expects DatetimeIndex)
            data = df.copy()
            if 'time' in data.columns:
                data['time'] = pd.to_datetime(data['time'])
                data.set_index('time', inplace=True)
            
            # Ensure index is sorted
            data.sort_index(inplace=True)

            img_path = os.path.join(self.export_dir, filename)
            
            # Basic Plotting Arguments
            kwargs = dict(
                type='candle',
                style='charles',
                title=f"\n{symbol} Analysis",
                ylabel='Price ($)',
                volume=False,
                savefig=img_path,
                figsize=(12, 8)
            )

            # Special Markers (MSS, Sweeps)
            # and horizontal lines (FVGs, Entry, SL, TP)
            hlines = []
            h_colors = []
            
            if zones:
                if 'trade' in zones:
                    t = zones['trade']
                    if 'entry' in t: 
                        hlines.append(t['entry'])
                        h_colors.append('blue')
                    if 'sl' in t: 
                        hlines.append(t['sl'])
                        h_colors.append('red')
                    if 'tp' in t: 
                        hlines.append(t['tp'])
                        h_colors.append('green')
                
                if 'sweeps' in zones:
                    for s in zones['sweeps']:
                        price = s.get('price', s.get('level'))
                        if price:
                            hlines.append(price)
                            h_colors.append('gold')

            if hlines:
                kwargs['hlines'] = dict(hlines=hlines, colors=h_colors, linestyle='-.')

            # Render
            mpf.plot(data, **kwargs)
            
            logger.info(f"Chart generated: {img_path}")
            return img_path

        except Exception as e:
            logger.error(f"Failed to generate mplfinance chart: {e}")
            return None
