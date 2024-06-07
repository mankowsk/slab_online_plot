import watchdog.events
import watchdog.observers
import time
import config
import numpy as np
from bokeh.layouts import widgetbox, column, row
from bokeh.models import Slider
import bokeh.plotting as plt
from bokeh.colors import named
from bokeh.models import Legend, LegendItem, Dropdown, CheckboxButtonGroup, CheckboxGroup, HoverTool, ColumnDataSource, Select, Slider, WheelZoomTool, Range1d, markers, Arrow, NormalHead, Panel, Tabs, ColumnDataSource, DataTable, TableColumn, Circle, Whisker, TeeHead, Paragraph
from bokeh.io import output_notebook, show, push_notebook, output_file, curdoc
#output_file("test.html")
from bokeh.events import Tap
from scipy.spatial.transform import Rotation
from scipy.linalg import det
from threading import Thread
from pathlib import Path

class Handler(watchdog.events.PatternMatchingEventHandler):
    def __init__(self, on_created_cb=None, on_modified_cb=None, document=None):
        watchdog.events.PatternMatchingEventHandler.__init__(self, patterns=['*run*.txt'], ignore_directories=True, case_sensitive=False)
        self.on_created_cb = on_created_cb
        self.on_modified_cb = on_modified_cb
        self.document = document

    def on_created(self, event):
        print("New file created - % s." % event.src_path)
        config.file_name = event.src_path
        if self.on_created_cb is not None:
            self.document.add_next_tick_callback(self.on_created_cb)

    def on_modified(self, event):
        #print("Watchdog received modified event - % s." % event.src_path)
        config.file_name = event.src_path
        if self.on_modified_cb is not None:
            self.document.add_next_tick_callback(self.on_modified_cb)

class Data_Visualization():
    def __init__(self):
        self._new_pgroup = False
        self.av = False
        self.setup_plot()
        self.observer_thread = Thread(target=self.watch_files, daemon=False)
        self.observer_thread.start()

    def watch_files(self):
        print("Starting")
        event_handler = Handler(on_created_cb=self.on_created_cb, on_modified_cb=self.on_modified_cb, document=self.document)
        self.observer = watchdog.observers.Observer()
        watch = self.observer.schedule(event_handler, path=self._src_path, recursive=True)
        self.observer.start()
        while True:
            time.sleep(.2)
            if self._new_pgroup:
                print("unschedule watch")
                self.observer.unschedule(watch)
                #self.observer.stop()
                #self.observer.join()
                #self.observer.unschedule(watch)
                print("schedule new watch")
                watch = self.observer.schedule(event_handler, path=self._src_path, recursive=True)
                #self.observer.start()
                self._new_pgroup=False

    def read_file(self, file_name):
        data = np.loadtxt(file_name)
        return data.T

    def create_color_palette(self, n, color):
        #if n<10:
        #    n=10
        nl = n-n//2
        nd = n//2
        colors = [color.darken(0.25-0.25*m/nd).to_rgb() for m in range(nd)]
        colors.extend([color.lighten(0.5*m/nl).to_rgb() for m in range(nl)])
        return colors
        


    def setup_plot(self):
        ### dropdown pgroup selection ###
        p = Path("/sf/slab/data/")
        menu = [d.stem for d in p.glob("*")] 
        dropdown = Dropdown(label = "Pgroup Selection", menu=menu)
        dropdown.on_click(self.on_change_pgroup_cb)
        #self._src_path = f"/sf/slab/data/{menu[-1]}/res/scan_data/"
        self._src_path = f"/sf/slab/config/eco/test_acq/scan_data/"


        ### check button channel selection ###
        labels = [f"Ch {n}" for n in range(8)]
        checkbox_button_group = CheckboxButtonGroup(labels=labels, active=[0])
        self.active_channels = [0]
        checkbox_button_group.on_change('active', self.on_change_selected_chs_cb)

        ### data table run selection ###
        self.table_source=None
        cols, data = self.get_run_table_data()
        self.table_source = ColumnDataSource(data)
        run_table = DataTable(width=700, source=self.table_source, columns=cols, height=400, selectable=True, index_position = None, autosize_mode="fit_columns")
        self.table_source.selected.on_change('indices', self.on_table_selected_cb)
        #self.table_source.on_event('Press', self.on_table_selected_cb)
        self.selected_runs = {}


        ### DD LOOP OVER 8 CHANNELS IN SOURCES (0...7)###
        self.colors = [named.__dict__[c] for c in ["darkblue", "blue", "blueviolet", "crimson", "darkorange", "gold", "green", "lightseagreen"]]
        colors = self.colors
        names=[]
        for n in range(8):
            for label in ["on", "off", "ratio"]:
                names.append(f"Ch{n} {label}")
        hover=HoverTool(names=names)
        for n in range(8):
            for label in ["on_av", "off_av", "ratio_av"]:
                names.append(f"Ch{n} {label}")
        hoverav=HoverTool(names=names)
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
            "selected": {
                "abs": {
                    "fig": plt.figure(height=400, tools=[hoverav,"pan,wheel_zoom,box_zoom,reset,save"], sizing_mode="stretch_both"),
                    #"fig": plt.figure(tools=[hoverav,"pan,wheel_zoom,box_zoom,reset,save"]),
                    "sources": {
                        "on": {n: ColumnDataSource(data=dict(xs=[[0,1,2],[1,2,3]], ys=[[1,2,3],[1,2,3]], labels=[f"Ch {n} 1",f"Ch {n} 2"], alpha=[1,1], colors=self.create_color_palette(2, self.colors[n]))) for n in range(8)},
                        "off": {n: ColumnDataSource(data=dict(xs=[[0,1,2],[1,2,3]], ys=[[1,2,3],[1,2,3]], alpha=[.5,.5], colors=self.create_color_palette(2, self.colors[n]))) for n in range(8)},
                        "on_av": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,1], upper=[.1,1.1], lower=[-.1,0.9])) for n in range(8)},
                        "off_av": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,0.9], upper=[.1,1], lower=[-.1,0.8])) for n in range(8)}
                        },
                    "lines": {
                        "on": {},
                        "off": {},
                        "on_av": {},
                        "off_av": {}
                        },
                    "markers": {
                        "on": {},
                        "off": {},
                        "on_av": {},
                        "off_av": {}
                        },
                    "errors": {
                        "on": {},
                        "off": {},
                        "on_av": {},
                        "off_av": {}
                        },
                    },
                "ratio": {
                    "fig": plt.figure(height=400, tools=[hoverav,"pan,wheel_zoom,box_zoom,reset,save"], sizing_mode="stretch_both"),
                    #"fig": plt.figure(tools=[hoverav,"pan,wheel_zoom,box_zoom,reset,save"]),
                    "sources": {
                        "ratio": {n: ColumnDataSource(data=dict(xs=[[0,1,2],[1,2,3]], ys=[[1,2,3],[1,2,3]], labels=[f"Ch {n} 1",f"Ch {n} 2"], alpha=[1,1], colors=self.create_color_palette(2, self.colors[n]))) for n in range(8)},
                        "ratio_av": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,.1], upper=[.1,0.2], lower=[-.1,0])) for n in range(8)},
                        },
                    "lines": {
                        "ratio": {},
                        "ratio_av": {}
                        },
                    "markers": {
                        "ratio": {},
                        "ratio_av": {}
                        },
                    "errors": {
                        "ratio": {},
                        "ratio_av": {}
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
                        if block == "selected":
                            if ~self.av:
                                if "av" in label:
                                    continue
                            if label =="off":
                                self.figures[block][panel]["lines"][label][ch]=fig.multi_line(source=source, line_color='colors', line_width=2, line_alpha='alpha')
                            elif label=="on":
                                self.figures[block][panel]["lines"][label][ch]=fig.multi_line(source=source, line_color='colors', line_width=2, line_alpha='alpha')
                                li = LegendItem()
                                li.label = {'field': 'labels'}
                                li.renderers=[self.figures[block][panel]["lines"][label][ch]]
                                lis.append(li)
                            elif label=="ratio":
                                self.figures[block][panel]["lines"][label][ch]=fig.multi_line(source=source, line_color='colors', line_width=2, line_alpha='alpha')
                                li = LegendItem()
                                li.label = {'field': 'labels'}
                                li.renderers=[self.figures[block][panel]["lines"][label][ch]]
                                lis.append(li)
                            elif label == "off_av":
                                self.figures[block][panel]["lines"][label][ch]=fig.line(source=source, line_color=colors[ch], line_width=4, line_alpha=.5)
                                self.figures[block][panel]["markers"][label][ch]=fig.circle(source=source, color=colors[ch], size=7, alpha=.5)
                                errors = Whisker(source=source, base='x', upper='upper', lower='lower', level="overlay",line_color=colors[ch], line_width=2, line_alpha=.5, upper_units='data', lower_units='data', upper_head=TeeHead(line_color=colors[ch], line_alpha=.5), lower_head=TeeHead(line_color=colors[ch], line_alpha=.5))
                                errors.upper_head.line_color = colors[ch]
                                errors.lower_head.line_color = colors[ch]
                                self.figures[block][panel]["errors"][label][ch]= errors
                                fig.add_layout(errors)
                            else:
                                self.figures[block][panel]["lines"][label][ch]=fig.line(source=source, line_color=colors[ch], line_width=4, line_alpha=1)
                                self.figures[block][panel]["markers"][label][ch]=fig.circle(source=source, color=colors[ch], size=7, alpha=1)
                                errors = Whisker(source=source, base='x', upper='upper', lower='lower', level="overlay",line_color=colors[ch], line_width=2, line_alpha=1, upper_units='data', lower_units='data', upper_head=TeeHead(line_color=colors[ch], line_alpha=1), lower_head=TeeHead(line_color=colors[ch], line_alpha=1))
                                self.figures[block][panel]["errors"][label][ch]= errors 
                                fig.add_layout(errors)

                        else:
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
        
        #col2 = column(dropdown, checkbox_button_group, *blocks, run_table, sizing_mode="stretch_width")
        col2 = column(dropdown, checkbox_button_group, Paragraph(text="Current Scan", align="center"), blocks[0], Paragraph(text="Selected Scans", align="center"), blocks[1], run_table, sizing_mode="stretch_width")
        #col1 = column(dropdown, checkbox_button_group, run_table)
        layout =col2
        self.document.add_root(layout)

    def get_run_table_data(self):
        p = Path(self._src_path)
        fs = p.rglob("*.txt")
        self.runs = {int(f.parts[-2][3:7]): f.as_posix() for f in fs if f.is_file()}
        fs = p.rglob("*.txt")
        data = {"selected": ["" for n in self.runs.keys()], "run": list(self.runs.keys()), "name":[f.stem for f in fs if f.is_file()]}

        cols = [TableColumn(field="selected", title="Selected"), TableColumn(field="run", title="Run Number"), TableColumn(field="name", title="Name")]
        return cols, data

    def calc_average_nobin(self, xs, ys, yerrs, nshots):
        xs = np.hstack(xs)
        nshots=np.hstack(nshots)
        ys = np.hstack(ys)*nshots
        yerrs = np.hstack(yerrs)*nshots
        xu = np.unique(xs)
        N = len(xu)//75
        xu = xu[::N]
        bins = xu +np.hstack([np.diff(xu), np.diff(xu)[-1]])
        idx = np.digitize(xs, xu, right=True)
        yu = np.array([np.sum(ys[idx==n])/np.sum(nshots[idx==n]) for n in range(len(bins))])
        yuerr = np.array([np.sum(yerrs[idx==n])/np.sum(nshots[idx==n]) for n in range(len(bins))])
        nshotsu = np.array([np.sum(nshots[idx==n]) for n in range(len(bins))])
        return xu, yu, yuerr/np.sqrt(nshotsu)


    ### callbacks
    def on_change_pgroup_cb(self,event):
        self._src_path = f"/sf/slab/data/{event.item}/res/scan_data/"
        cols, data = self.get_run_table_data()
        self.table_source.data = data
        self.selected_runs={}
        self._new_pgroup = True
        pass

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
 
                                

    def on_table_selected_cb(self, attrname, old, new):
        if len(self.table_source.selected.indices) > 0:
            idx = self.table_source.selected.indices[0]
        else:
            return

        run = self.table_source.data["run"][idx]
        sel = self.table_source.data["selected"]
        if run in self.selected_runs.keys():
            run = self.selected_runs.pop(run)
            sel[idx]=""
            self.table_source.data["selected"]=sel
        else: 
            self.selected_runs[run]=self.runs[run]
            sel[idx]="X"
            self.table_source.data["selected"]=sel
        xs={n: [] for n in range(8)}
        nonshots={n: [] for n in range(8)}
        noffshots={n: [] for n in range(8)}
        yons={n: [] for n in range(8)}
        yoffs={n: [] for n in range(8)}
        yratios={n: [] for n in range(8)}
        yons_err={n: [] for n in range(8)}
        yoffs_err={n: [] for n in range(8)}

        block = self.figures["selected"]
        sd =  {key: val for key, val in sorted(self.selected_runs.items(), key = lambda ele: ele[1])}
        labs = [f'Run{k}' for k in sd.keys()]
        for key, fpath in sd.items():
            data = self.read_file(fpath)
            nadj = data.shape[0]-48
            for n in range(8):
                xs[n].append(data[0])
                nonshots[n].append(data[nadj+n+32])
                noffshots[n].append(data[nadj+n+32+8])
                yons[n].append(data[nadj+n])
                yoffs[n].append(data[nadj+n+8])
                yratios[n].append(data[nadj+n]/data[nadj+n+8])
                yons_err[n].append(data[nadj+n+16])
                yoffs_err[n].append(data[nadj+n+8+16])
        for n in range(8):
            block["abs"]["sources"]["on"][n].data=dict(xs=xs[n], ys=yons[n], alpha=np.full([(len(self.selected_runs.items()))],1), colors=self.create_color_palette(len(self.selected_runs),self.colors[n]), labels=[f'Ch{n} {l}' for l in labs])
            block["abs"]["sources"]["off"][n].data=dict(xs=xs[n], ys=yoffs[n], alpha=np.full([(len(self.selected_runs.items()))],.5), colors=self.create_color_palette(len(self.selected_runs),self.colors[n]))
            block["ratio"]["sources"]["ratio"][n].data=dict(xs=xs[n], ys=yratios[n], colors=self.create_color_palette(len(self.selected_runs),self.colors[n]), labels=[f'Ch{n} {l}' for l in labs])
            if self.av:
                x,yon,yon_err = self.calc_average_nobin(xs[n],yons[n],yons_err[n],nonshots[n])
                block["abs"]["sources"]["on_av"][n].data=dict(x=x, y=yon, upper=yon+yon_err, lower=yon-yon_err)
                x,yoff,yoff_err = self.calc_average_nobin(xs[n],yoffs[n],yoffs_err[n],noffshots[n])
                block["abs"]["sources"]["off_av"][n].data=dict(x=x, y=yoff, upper=yoff+yoff_err, lower=yoff-yoff_err)
                yratio_err = np.sqrt((yon_err/yoff)**2+(yon/yoff**2*yoff_err)**2)
                block["ratio"]["sources"]["ratio_av"][n].data=dict(x=x, y=yon/yoff, upper=yon/yoff+yratio_err, lower=yon/yoff-yratio_err)
        self.table_source.selected.indices=[]

    def on_created_cb(self):
        cols, data = self.get_run_table_data()
        data["selected"] = self.table_source.data["selected"]
        self.table_source.data = data

    def on_modified_cb(self):
        data = self.read_file(config.file_name)
        if len(data.shape)>1:
            block = self.figures["current"]
            nadj = data.shape[0]-48
            for n in range(8):
                x, yon, yoff, yon_std, yoff_std, yon_nshots, yoff_nshots =data[[0,nadj+n,nadj+n+8,nadj+n+16,nadj+n+24,nadj+n+32,nadj+n+40],:]
                yon_err = yon_std/np.sqrt(yon_nshots)
                yoff_err = yoff_std/np.sqrt(yoff_nshots)
                yratio_err = np.sqrt((yon_err/yoff)**2+(yon/yoff**2*yoff_err)**2)
                block["abs"]["sources"]["on"][n].data=dict(x=x, y=yon, upper=yon+yon_err, lower=yon-yon_err)
                block["abs"]["sources"]["off"][n].data=dict(x=x, y=yoff, upper=yoff+yoff_err, lower=yoff-yoff_err)
                block["ratio"]["sources"]["ratio"][n].data=dict(x=x, y=yon/yoff, upper=yon/yoff + yratio_err, lower = yon/yoff - yratio_err)
    
dv = Data_Visualization()





