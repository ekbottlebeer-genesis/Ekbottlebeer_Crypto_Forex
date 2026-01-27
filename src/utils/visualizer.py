import logging
import os
import pandas as pd
import mplfinance as mpf
import numpy as np
import matplotlib
matplotlib.use('Agg') # Force non-GUI backend for stability
import matplotlib.pyplot as plt

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
            
            # 1. Custom TradingView Style
            mc = mpf.make_marketcolors(up='#089981', down='#f23645', # TV Official Colors
                                       edge='inherit',
                                       wick='inherit',
                                       volume='in',
                                       ohlc='inherit')
            s  = mpf.make_mpf_style(marketcolors=mc, 
                                   facecolor='#131722', 
                                   gridcolor='#2a2e39', 
                                   gridstyle='solid',
                                   edgecolor='#2a2e39',
                                   y_on_right=True)

            # 2. Horizontal Lines Logic
            hlines = []
            h_colors = []
            h_styles = []
            
            if zones:
                # Execution Context
                if 'trade' in zones:
                    t = zones['trade']
                    if t.get('entry'): hlines.append(t['entry']); h_colors.append('#2962ff'); h_styles.append('-') # Blue Entry
                    if t.get('sl'): hlines.append(t['sl']); h_colors.append('#f23645'); h_styles.append('--')     # Red SL
                    if t.get('tp'): hlines.append(t['tp']); h_colors.append('#089981'); h_styles.append('-')     # Green TP
                
                # HTF Range Context (User Request)
                if 'htf' in zones:
                    htf = zones['htf']
                    if htf.get('1H_high'): hlines.append(htf['1H_high']); h_colors.append('#ff9800'); h_styles.append('-.') # Orange 1H High
                    if htf.get('1H_low'): hlines.append(htf['1H_low']); h_colors.append('#ff9800'); h_styles.append('-.')   # Orange 1H Low
                    if htf.get('4H_high'): hlines.append(htf['4H_high']); h_colors.append('#9c27b0'); h_styles.append(':')  # Purple 4H High
                    if htf.get('4H_low'): hlines.append(htf['4H_low']); h_colors.append('#9c27b0'); h_styles.append(':')    # Purple 4H Low

                if 'sweeps' in zones:
                    for s_zone in zones['sweeps']:
                        price = s_zone.get('price', s_zone.get('level'))
                        if price:
                            hlines.append(price)
                            h_colors.append('#ffd600') # Gold Sweep
                            h_styles.append('-')
                
                if 'mss' in zones:
                     # Check if it's a list or single dict
                     mss_zones = zones['mss'] if isinstance(zones['mss'], list) else [zones['mss']]
                     for m_zone in mss_zones:
                         price = m_zone.get('level', m_zone.get('price'))
                         if price:
                             hlines.append(price)
                             h_colors.append('#ffffff') # White MSS
                             h_styles.append('--')      # Dashed

            # Basic Plotting Arguments
            kwargs = dict(
                type='candle',
                style=s,
                title=f"\n{symbol} - Tactical View",
                ylabel='Price',
                volume=False,
                savefig=img_path,
                figsize=(15, 10),
                datetime_format='%H:%M',
                xrotation=0,
                tight_layout=True,
                scale_padding=dict(left=0.1, right=1.2, top=0.5, bottom=0.5)
            )

            if hlines:
                kwargs['hlines'] = dict(hlines=hlines, colors=h_colors, linestyle=h_styles, linewidths=1.8)

            # 4. Render
            mpf.plot(data, **kwargs)
            
            logger.info(f"Professional Tactical Chart generated: {img_path}")
            return img_path

        except Exception as e:
            logger.error(f"Failed to generate professional chart: {e}")
            return None
