import numpy as np
from epics import PV
from bokeh.layouts import widgetbox, column, row
from bokeh.models import Slider
import bokeh.plotting as plt
from bokeh.colors import named
from bokeh.models import Legend, LegendItem, Dropdown, CheckboxButtonGroup, CheckboxGroup, HoverTool, ColumnDataSource, Select, Slider, WheelZoomTool, Range1d, markers, Arrow, NormalHead, Panel, Tabs, ColumnDataSource, DataTable, TableColumn, Circle, Whisker, TeeHead
from bokeh.io import output_notebook, show, push_notebook, output_file, curdoc
#output_file("test.html")
from bokeh.events import Tap
from scipy.spatial.transform import Rotation
from scipy.linalg import det
from threading import Thread
from pathlib import Path
import time
from collections import deque
from threading import Thread
import os
os.sys.path.insert(0,"/sf/slab/config/src/python/eco/")
from eco.acquisition.ioxos_slab import Slab_Ioxos, Slab_Ioxos_Daq



class Data_Visualization():
    def __init__(self):
        self.ioxos = Slab_Ioxos(name="ioxos", pvbase = "SLAB-LSCP1-ESB1")
        self.daq = Slab_Ioxos_Daq(name="ioxos_daq", default_file_path="", ioxos =self.ioxos)
        self._running = True
        self.nshots=100
        self.data=np.ndarray((48,50))
        self.setup_plot()
        self.accumulator = Thread(target=self.run_continuously, daemon=False)
        self.accumulator.start()


    def average_data(self, data, N_pulses):
        chopper_chs = [self.ioxos.__dict__[f"ch{n}"].chopper_ch() for n in range(8)]
        chopper_thrs = [self.ioxos.__dict__[f"ch{n}"].chopper_thr() for n in range(8)]
        chopper_invs = [self.ioxos.__dict__[f"ch{n}"].chopper_inv() for n in range(8)]
        w = np.array([data[ch]<thr if inv else data[ch]>thr for ch, thr, inv in zip(chopper_chs, chopper_thrs, chopper_invs)])
        d_av_on = np.mean(data, axis=1, where=w)
        d_av_off = np.mean(data, axis=1, where=~w)
        d_std_on = np.std(data, axis=1, where=w)
        d_std_off = np.std(data, axis=1, where=~w)
        d_npulses_on = np.sum(w, axis=1)
        d_npulses_off = np.sum(~w, axis=1)
        d = np.hstack([d_av_on, d_av_off, d_std_on, d_std_off, d_npulses_on, d_npulses_off])
        return d

    def run_continuously(self):
        while(True):
            cnt = 0
            while self._running:
                d_raw = self.daq.get_data(N_pulses =  self.nshots)
                d_av = self.average_data(d_raw, N_pulses =  self.nshots)
                cnt = cnt+1
                self.data = np.roll(self.data, -1, axis=1)
                self.data[:,-1] = d_av
                if cnt == 3:
                    self.document.add_next_tick_callback(self.on_modified_cb)
                    cnt=0

    def on_modified_cb(self):
        data = self.data
        if len(data.shape)>1:
            block = self.figures["current"]
            for n in range(8):
                yon, yoff, yon_std, yoff_std, yon_nshots, yoff_nshots =data[[n,n+8,n+16,n+24,n+32,n+40],:]
                x = np.arange(len(yon))*self.nshots
                yon_err = yon_std/np.sqrt(yon_nshots)
                yoff_err = yoff_std/np.sqrt(yoff_nshots)
                yratio_err = np.sqrt((yon_err/yoff)**2+(yon/yoff**2*yoff_err)**2)
                block["abs"]["sources"]["on"][n].data=dict(x=x, y=yon, upper=yon+yon_err, lower=yon-yon_err)
                block["abs"]["sources"]["off"][n].data=dict(x=x, y=yoff, upper=yoff+yoff_err, lower=yoff-yoff_err)
                block["ratio"]["sources"]["ratio"][n].data=dict(x=x, y=yon/yoff, upper=yon/yoff + yratio_err, lower = yon/yoff - yratio_err)

    def create_color_palette(self, n, color):
        #if n<10:
        #    n=10
        nl = n-n//2
        nd = n//2
        colors = [color.darken(0.25-0.25*m/nd).to_rgb() for m in range(nd)]
        colors.extend([color.lighten(0.5*m/nl).to_rgb() for m in range(nl)])
        return colors

    def setup_plot(self):
        ### check button channel selection ###
        labels = [f"Ch {n}" for n in range(8)]
        checkbox_button_group = CheckboxButtonGroup(labels=labels, active=[0])
        self.active_channels = [0]
        checkbox_button_group.on_change('active', self.on_change_selected_chs_cb)

        ### DD LOOP OVER 8 CHANNELS IN SOURCES (0...7)###
        self.colors = [named.__dict__[c] for c in ["darkblue", "blue", "blueviolet", "crimson", "darkorange", "gold", "green", "lightseagreen"]]
        colors = self.colors
        names=[]
        for n in range(8):
            for label in ["on", "off", "ratio"]:
                names.append(f"Ch{n} {label}")
        hover=HoverTool(names=names)
        self.figures = {
            "current": {
                "abs": {
                    "fig": plt.figure(tools=[hover,"pan,wheel_zoom,box_zoom,reset,save"], sizing_mode="stretch_both"),
                    "sources": {
                        "on": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,1], upper=[.1,1.1], lower=[-.1,0.9], labels=[f"Ch {n}"])) for n in range(8)},
                        "off": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,0.9], upper=[.1,1], lower=[-.1,0.8])) for n in range(8)}
                        },
                    "lines": {
                        "on": {},
                        "off": {},
                        },
                    "markers": {
                        "on": {},
                        "off": {},
                        },
                    "errors": {
                        "on": {},
                        "off": {},
                        },
                    },
                "ratio": {
                    "fig": plt.figure(tools=[hover,"pan,wheel_zoom,box_zoom,reset,save"], sizing_mode="stretch_both"),
                    "sources": {
                        "ratio": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,.1], upper=[.1,0.2], lower=[-.1,0], labels=[f"Ch {n}"])) for n in range(8)},
                        },
                    "lines": {
                        "ratio": {},
                        },
                    "markers": {
                        "ratio": {},
                        },
                    "errors": {
                        "ratio": {},
                        },
                    "legend": {
                        "ratio": {},
                       },
                    },
                },
        }

        blocks = []
        for block, val in self.figures.items():
            tabs = []
            for panel, dat in val.items():
                fig = dat["fig"]
                fig.y_range.only_visible = True
                fig.x_range.only_visible = True
                lis = []
                for label, chdat in dat["sources"].items():
                    for ch, source in chdat.items():
                        if label == "off":
                            self.figures[block][panel]["lines"][label][ch]=fig.line(source=source, line_color=colors[ch], line_width=2, line_alpha=.5)
                            self.figures[block][panel]["markers"][label][ch]=fig.circle(source=source, color=colors[ch], size=7, alpha=.5)
                            errors = Whisker(source=source, base='x', upper='upper', lower='lower', level="overlay",line_color=colors[ch], line_width=2, line_alpha=.5, upper_units='data', lower_units='data', upper_head=TeeHead(line_color=colors[ch], line_alpha=.5), lower_head=TeeHead(line_color=colors[ch], line_alpha=.5))
                            errors.upper_head.line_color = colors[ch]
                            errors.lower_head.line_color = colors[ch]
                            self.figures[block][panel]["errors"][label][ch]= errors
                            fig.add_layout(errors)
                        else:
                            self.figures[block][panel]["lines"][label][ch]=fig.line(source=source, line_color=colors[ch], line_width=2, line_alpha=1, legend_label=f"Ch {ch}", name=f"Ch{n} {label}")
                            self.figures[block][panel]["markers"][label][ch]=fig.circle(source=source, color=colors[ch], size=7, alpha=1)
                            errors = Whisker(source=source, base='x', upper='upper', lower='lower', level="overlay",line_color=colors[ch], line_width=2, line_alpha=1, upper_units='data', lower_units='data', upper_head=TeeHead(line_color=colors[ch], line_alpha=1), lower_head=TeeHead(line_color=colors[ch], line_alpha=1))
                            self.figures[block][panel]["errors"][label][ch]= errors 
                            fig.add_layout(errors)
                if len(lis) > 0:
                    legend = Legend(items = lis)
                    fig.add_layout(legend)
                    #fig.legend.items = lis
                self.figures[block][panel]["legend"]=fig.legend

                tabs.append(Panel(child=fig, title=panel))
            blocks.append(Tabs(tabs=tabs, sizing_mode="scale_width"))
        self.document =curdoc()
        
        col2 = column(checkbox_button_group, *blocks, sizing_mode="stretch_width")
        #col1 = column(dropdown, checkbox_button_group, run_table)
        layout =col2
        self.document.add_root(layout)

    def on_change_selected_chs_cb(self, attrname, old, new):
        self.active_channels = new
        #just need to set visibility
        for block, val in self.figures.items():
            for panel, dat in val.items():
                fig = dat["fig"]
                legend_items = fig.legend.items
                act_ids = []
                for obj in ["lines", "markers", "errors"]:
                    for label, linedat in dat[obj].items():
                        for ch, line in linedat.items():
                            lineid = line.id
                            if ch in self.active_channels:
                                line.visible=True
                                act_ids.append(lineid)
                            else:
                                line.visible = False
                for li in legend_items:
                    if li.renderers[0].id in act_ids:
                        li.label = {"field": "labels"}
                    else:
                        li.label = {"value": None}

dv = Data_Visualization()
