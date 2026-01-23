import logging
import os
import pandas as pd
import mplfinance as mpf
import numpy as np

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
            mc = mpf.make_marketcolors(up='#26a69a', down='#ef5350',
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

            # 2. Swing Point Detection (For Annotations)
            # Find local high/low (3-candle pivot)
            sh_vals = []
            sl_vals = []
            for i in range(1, len(data)-1):
                # Swing High
                if data['high'].iloc[i] > data['high'].iloc[i-1] and data['high'].iloc[i] > data['high'].iloc[i+1]:
                    sh_vals.append(data['high'].iloc[i] * 1.001) # SLightly above
                else:
                    sh_vals.append(np.nan)
                
                # Swing Low
                if data['low'].iloc[i] < data['low'].iloc[i-1] and data['low'].iloc[i] < data['low'].iloc[i+1]:
                    sl_vals.append(data['low'].iloc[i] * 0.999) # Slightly below
                else:
                    sl_vals.append(np.nan)
            
            # Pad ends
            sh_series = [np.nan] + sh_vals + [np.nan]
            sl_series = [np.nan] + sl_vals + [np.nan]

            apds = []
            apds.append(mpf.make_addplot(sh_series, type='scatter', markersize=50, marker='v', color='#ff9800'))
            apds.append(mpf.make_addplot(sl_series, type='scatter', markersize=50, marker='^', color='#2196f3'))

            # 3. Horizontal Lines & Labels
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
                    for s_zone in zones['sweeps']:
                        price = s_zone.get('price', s_zone.get('level'))
                        if price:
                            hlines.append(price)
                            h_colors.append('gold')

            # Basic Plotting Arguments
            kwargs = dict(
                type='candle',
                style=s,
                title=f"\n{symbol} (M5) - The A+ Operator",
                ylabel='Price',
                volume=False,
                addplot=apds,
                savefig=img_path,
                figsize=(14, 9),
                datetime_format='%H:%M',
                xrotation=0,
                tight_layout=True
            )

            if hlines:
                kwargs['hlines'] = dict(hlines=hlines, colors=h_colors, linestyle='-.', linewidths=1.5)

            # 4. Render
            mpf.plot(data, **kwargs)
            
            logger.info(f"Professional Chart generated: {img_path}")
            return img_path

        except Exception as e:
            logger.error(f"Failed to generate professional chart: {e}")
            return None
