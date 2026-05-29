import watchdog.events
import watchdog.observers
import time
import config
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import Slider
import bokeh.plotting as plt
from bokeh.colors import named
from bokeh.models import Legend, LegendItem, Dropdown, CheckboxButtonGroup, CheckboxGroup, HoverTool, ColumnDataSource, Select, Slider, WheelZoomTool, Range1d, Arrow, NormalHead, ColumnDataSource, DataTable, TableColumn, Circle, Whisker, TeeHead, Paragraph
from bokeh.models.layouts import TabPanel, Tabs
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
        p = Path("/slab/data/")

        menu = [d.stem for d in p.glob("*")] 
        dropdown = Dropdown(label = "Pgroup Selection", menu=menu, sizing_mode="stretch_width")
        dropdown.on_click(self.on_change_pgroup_cb)
        #self._src_path = f"/slab/data/{menu[-1]}/res/scan_data/"
        self._src_path = f"/slab/config/eco/test_acq/scan_data/"


        ### check button channel selection ###
        labels = [f"Ch {n}" for n in range(8)]
        checkbox_button_group = CheckboxButtonGroup(labels=labels, active=[0], sizing_mode="stretch_width")
        self.active_channels = [0]
        checkbox_button_group.on_change('active', self.on_change_selected_chs_cb)

        ### checkbox for showing averages ###
        show_averages_checkbox = CheckboxGroup(labels=["Show averaged data (median)"], active=[0], sizing_mode="stretch_width")
        show_averages_checkbox.on_change('active', self.on_show_averages_cb)
        self.show_averages = True

        ### data table run selection ###
        self.table_source=None
        cols, data = self.get_run_table_data()
        self.table_source = ColumnDataSource(data)
        run_table = DataTable(source=self.table_source, columns=cols, min_height=250, selectable=True, index_position = None, sizing_mode="stretch_both")#, autosize_mode="fit_columns")
        self.table_source.selected.on_change('indices', self.on_table_selected_cb)
        #self.table_source.on_event('Press', self.on_table_selected_cb)
        self.selected_runs = {}


        ### DD LOOP OVER 8 CHANNELS IN SOURCES (0...7)###
        self.colors = [named.__dict__[c] for c in ["darkblue", "blue", "blueviolet", "crimson", "darkorange", "gold", "green", "lightseagreen"]]
        colors = self.colors

        hover_tool = HoverTool(
            tooltips=[
                ("Run/Ch", "@labels"),
                ("X", "$x"),
                ("Y", "$y"),
            ],
            mode='vline', # This makes it easier to "hit" a line by just being at the same X
            line_policy = 'interp',
        )
        from bokeh.models.tools import CustomJSHover
        
        # JS for X-coordinate
        code = """
            const si = special_vars.segment_index;
            return value[si].toPrecision(4);
        """
        custom_hover = CustomJSHover(code=code)

        hover_tool_selected = HoverTool(
        tooltips=[
                ("Run", "@labels"),
                ("X", "@xs{custom}"), # Use @xs but process it with 'custom'
                ("Y", "@ys{custom}"),
            ],
            formatters={
                "@xs": custom_hover,
                "@ys": custom_hover
            },
            line_policy = 'nearest',
            mode='mouse',
            point_policy="snap_to_data",
            attachment='vertical' 
        )


        self.figures = {
            "current": {
                "abs": {
                    "fig": plt.figure(tools=["pan,wheel_zoom,box_zoom,reset,save",hover_tool], sizing_mode="stretch_both"),#hover
                    "sources": {
                        "on": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,1], upper=[.1,1.1], lower=[-.1,0.9], labels=[f"Ch {n}"])) for n in range(8)},
                        #"on": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,1], upper=[.1,1.1], lower=[-.1,0.9])) for n in range(8)},
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
                    "fig": plt.figure(tools=["pan,wheel_zoom,box_zoom,reset,save", hover_tool], sizing_mode="stretch_both"),#hover
                    "sources": {
                        "ratio": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,.1], upper=[.1,0.2], lower=[-.1,0], labels=[f"Ch {n}"])) for n in range(8)},
                        #"ratio": {n: ColumnDataSource(data=dict(x=[0,1], y=[0,.1], upper=[.1,0.2], lower=[-.1,0])) for n in range(8)},
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
                    "fig": plt.figure(tools=["pan,wheel_zoom,box_zoom,reset,save", hover_tool_selected], sizing_mode="stretch_both"),#hoverav
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
                    "fig": plt.figure(tools=["pan,wheel_zoom,box_zoom,reset,save", hover_tool_selected], sizing_mode="stretch_both"),#hoverav
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
                if block == "selected":
                    leg = Legend(items=[])
                    fig.add_layout(leg)
                for label, chdat in dat["sources"].items():
                    for n, (ch, source) in enumerate(chdat.items()):
                        if block == "selected":
                            if not self.av:
                                if "av" in label:
                                    continue
                            if label =="off":
                                self.figures[block][panel]["lines"][label][ch]=fig.multi_line(xs='xs',ys='ys',source=source, line_color='colors', line_width=2, line_alpha='alpha')
                            elif label=="on":
                                self.figures[block][panel]["lines"][label][ch]=fig.multi_line(xs='xs',ys='ys',source=source, line_color='colors', line_width=2, line_alpha='alpha')

                            elif label=="ratio":
                                self.figures[block][panel]["lines"][label][ch]=fig.multi_line(xs='xs',ys='ys',source=source, line_color='colors', line_width=2, line_alpha='alpha')

                            elif label == "off_av":
                                self.figures[block][panel]["lines"][label][ch]=fig.line(x='x',y='y',source=source, line_color=colors[ch], line_width=4, line_alpha=.5)
                                self.figures[block][panel]["markers"][label][ch]=fig.scatter(x='x',y='y',source=source, color=colors[ch], size=7, alpha=.5, marker="circle")
                                errors = Whisker(source=source, base='x', upper='upper', lower='lower', level="overlay",line_color=colors[ch], line_width=2, line_alpha=.5, upper_units='data', lower_units='data', upper_head=TeeHead(line_color=colors[ch], line_alpha=.5), lower_head=TeeHead(line_color=colors[ch], line_alpha=.5))
                                errors.upper_head.line_color = colors[ch]
                                errors.lower_head.line_color = colors[ch]
                                self.figures[block][panel]["errors"][label][ch]= errors
                                fig.add_layout(errors)
                            else:
                                self.figures[block][panel]["lines"][label][ch]=fig.line(x='x',y='y',source=source, line_color=colors[ch], line_width=4, line_alpha=1)
                                self.figures[block][panel]["markers"][label][ch]=fig.scatter(x='x',y='y',source=source, color=colors[ch], size=7, alpha=1, marker="circle")
                                errors = Whisker(source=source, base='x', upper='upper', lower='lower', level="overlay",line_color=colors[ch], line_width=2, line_alpha=1, upper_units='data', lower_units='data', upper_head=TeeHead(line_color=colors[ch], line_alpha=1), lower_head=TeeHead(line_color=colors[ch], line_alpha=1))
                                self.figures[block][panel]["errors"][label][ch]= errors 
                                fig.add_layout(errors)

                        else:
                            if label == "off":
                                self.figures[block][panel]["lines"][label][ch]=fig.line(x='x',y='y',source=source, line_color=colors[ch], line_width=2, line_alpha=.5)
                                self.figures[block][panel]["markers"][label][ch]=fig.scatter(x='x',y='y',source=source, color=colors[ch], size=7, alpha=.5, marker="circle")
                                errors = Whisker(source=source, base='x', upper='upper', lower='lower', level="overlay",line_color=colors[ch], line_width=2, line_alpha=.5, upper_units='data', lower_units='data', upper_head=TeeHead(line_color=colors[ch], line_alpha=.5), lower_head=TeeHead(line_color=colors[ch], line_alpha=.5))
                                errors.upper_head.line_color = colors[ch]
                                errors.lower_head.line_color = colors[ch]
                                self.figures[block][panel]["errors"][label][ch]= errors
                                fig.add_layout(errors)
                            else:
                                self.figures[block][panel]["lines"][label][ch]=fig.line(x='x',y='y',source=source, line_color=colors[ch], line_width=2, line_alpha=1, legend_label=f"Ch {ch}", name=f"Ch{n} {label}")
                                self.figures[block][panel]["markers"][label][ch]=fig.scatter(x='x',y='y',source=source, color=colors[ch], size=7, alpha=1, marker="circle")
                                errors = Whisker(source=source, base='x', upper='upper', lower='lower', level="overlay",line_color=colors[ch], line_width=2, line_alpha=1, upper_units='data', lower_units='data', upper_head=TeeHead(line_color=colors[ch], line_alpha=1), lower_head=TeeHead(line_color=colors[ch], line_alpha=1))
                                self.figures[block][panel]["errors"][label][ch]= errors 
                                fig.add_layout(errors)


                tabs.append(TabPanel(child=fig, title=panel))
            blocks.append(Tabs(tabs=tabs, sizing_mode="stretch_both", min_height=200))#, sizing_mode="stretch_width"))
        self.document =curdoc()
        
        #col2 = column(dropdown, checkbox_button_group, *blocks, run_table, sizing_mode="stretch_width")
        col2 = column(show_averages_checkbox, dropdown, checkbox_button_group, Paragraph(text="Current Scan", align="center"), blocks[0], Paragraph(text="Selected Scans", align="center"), blocks[1], run_table, sizing_mode="stretch_both", min_height=1200)#sizing_mode="stretch_width")
        #col2 = column(dropdown, fig, run_table)
        layout =col2
        self.document.add_root(layout)

    def get_run_table_data(self):
        p = Path(self._src_path)
        fs = p.rglob("*.txt")
        self.runs={}
        names={}
        for f in fs:
            if f.is_file():
                run_number = int(f.parts[-2][3:7])
                self.runs[run_number] = f.as_posix()
                names[run_number] = f.stem
        data = {"selected": ["" for n in self.runs.keys()], "run": list(self.runs.keys()), "name":list(names.items())}
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

    def calculate_aggregated_averages(self, xs_dict, ys_dict, yerrs_dict=None, use_median=True):
        """
        Calculate aggregated average (mean or median) over selected runs with intelligent binning.

        Args:
            xs_dict: dict mapping channel -> list of x arrays (one per run)
            ys_dict: dict mapping channel -> list of y arrays (one per run)
            yerrs_dict: optional dict mapping channel -> list of yerr arrays (one per run)
            use_median: if True use median, otherwise use mean

        Returns:
            dict mapping channel -> (x_binned, y_avg, y_err) for binned aggregated data
        """
        result = {}

        for ch in xs_dict.keys():
            all_xs = xs_dict[ch]  # list of arrays
            all_ys = ys_dict[ch]  # list of arrays

            # Collect all unique x values across runs
            x_conc = np.concatenate(all_xs)
            x_unique = np.unique(x_conc)

            if len(x_unique) < 2:
                # Not enough data points to bin
                result[ch] = (x_unique, np.nan, np.nan)
                continue

            # Remove values that are too close to each other
            x_diffs = np.diff(x_unique)
            x_min_gap = np.min(np.abs(x_diffs))

            # Keep only x values where the gap to next is >= min gap (with small tolerance)
            if len(x_diffs) > 0:
                x_bin_mask = x_diffs >= (x_min_gap * 0.5)  # 50% tolerance for removing close points
                x_binned = np.concatenate([x_unique[:-1][x_bin_mask], [x_unique[-1]]])
            else:
                x_binned = x_unique

            if len(x_binned) < 2:
                result[ch] = (x_binned, np.nan, np.nan)
                continue

            # For each bin center, collect all y values from runs that have data near this x
            y_values_list = []
            for run_idx, (xs_run, ys_run) in enumerate(zip(all_xs, all_ys)):
                # Find indices where this run has data close to binned x values
                for xb in x_binned:
                    # Find points within a small tolerance of the bin center
                    mask = np.abs(xs_run - xb) < (np.min(np.diff(x_binned)) / 2 if len(x_binned) > 1 else 1.0)
                    if np.any(mask):
                        y_values_list.append(ys_run[mask])

            if not y_values_list:
                result[ch] = (x_binned, np.nan, np.nan)
                continue

            # Stack all y values for each bin and compute median/mean
            y_avg_list = []
            y_err_list = []

            for xb in x_binned:
                # Collect all y values near this bin center across all runs
                nearby_ys = []
                for xs_run, ys_run in zip(all_xs, all_ys):
                    mask = np.abs(xs_run - xb) < (np.min(np.diff(x_binned)) / 2 if len(x_binned) > 1 else 1.0)
                    if np.any(mask):
                        nearby_ys.extend(ys_run[mask])

                if len(nearby_ys) > 0:
                    nearby_ys = np.array(nearby_ys)
                    if use_median:
                        y_avg = np.median(nearby_ys)
                        # Use MAD (median absolute deviation) as error estimate, scaled for normal distribution
                        mad = np.median(np.abs(nearby_ys - y_avg))
                        y_err = mad * 1.4826 if mad > 0 else 0.0
                    else:
                        y_avg = np.mean(nearby_ys)
                        y_err = np.std(nearby_ys) / np.sqrt(len(nearby_ys)) if len(nearby_ys) > 1 else 0.0

                    y_avg_list.append(y_avg)
                    y_err_list.append(y_err)
                else:
                    y_avg_list.append(np.nan)
                    y_err_list.append(0.0)

            result[ch] = (x_binned, np.array(y_avg_list), np.array(y_err_list))

        return result


    ### callbacks
    def on_change_pgroup_cb(self,event):
        self._src_path = f"/slab/data/{event.item}/data/scan_data/"
        cols, data = self.get_run_table_data()
        self.table_source.data = data
        self.selected_runs={}
        self._new_pgroup = True
        pass

    def on_change_selected_chs_cb(self, attrname, old, new):
        self.active_channels = new
        for block_key, block_val in self.figures.items():
            for panel_key, dat in block_val.items():
                # Update Glyph Visibility
                for obj in ["lines", "markers", "errors"]:
                    for label, linedat in dat[obj].items():
                        for ch, line in linedat.items():
                            line.visible = (ch in self.active_channels)
                
                # Handle Legends differently per block
                if block_key == "current":
                    # Keep your original logic for the current block
                    for li in dat["fig"].legend.items:
                        if li.renderers[0].name and "Ch" in li.renderers[0].name:
                            ch_idx = int(li.renderers[0].name.split()[0][2:]) # Extracting N from "ChN"
                            li.visible = (ch_idx in self.active_channels)
                else:
                    # Refresh the 'selected' block legend to use a new proxy channel 
                    # if the old one was hidden
                    self.on_table_selected_cb(None, None, None)


    def on_show_averages_cb(self, attrname, old, new):
        """Toggle visibility of averaged data."""
        self.show_averages = len(new) > 0
        # Re-trigger the table selection callback to update visibility
        if len(self.selected_runs) > 0:
            self.on_table_selected_cb(attrname, old, new)

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

        selected_block = self.figures["selected"]
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
            selected_block["abs"]["sources"]["on"][n].data=dict(xs=xs[n], ys=yons[n], alpha=np.full([(len(self.selected_runs.items()))],1), colors=self.create_color_palette(len(self.selected_runs),self.colors[n]))
            selected_block["abs"]["sources"]["off"][n].data=dict(xs=xs[n], ys=yoffs[n], alpha=np.full([(len(self.selected_runs.items()))],.5), colors=self.create_color_palette(len(self.selected_runs),self.colors[n]))
            selected_block["ratio"]["sources"]["ratio"][n].data=dict(xs=xs[n], ys=yratios[n], colors=self.create_color_palette(len(self.selected_runs),self.colors[n]), alpha=np.full([(len(self.selected_runs.items()))], 1))

            # Conditionally add aggregated average lines (median) if checkbox is enabled
            if self.show_averages:
                # Prepare data for aggregated averages using new function
                xs_dict = {n: np.array(xs[n]) for n in range(8)}
                ys_on_dict = {n: np.array(yons[n]) for n in range(8)}
                ys_off_dict = {n: np.array(yoffs[n]) for n in range(8)}
                yratios_dict = {n: np.array(yratios[n]) for n in range(8)}

                # Calculate aggregated averages (median) with intelligent binning
                avg_on = self.calculate_aggregated_averages(xs_dict, ys_on_dict, use_median=True)
                avg_off = self.calculate_aggregated_averages(xs_dict, ys_off_dict, use_median=True)
                avg_ratio = self.calculate_aggregated_averages(xs_dict, yratios_dict, use_median=True)

                x_on_av, yon_av, yon_err = avg_on[n]
                selected_block["abs"]["sources"]["on_av"][n].data=dict(x=x_on_av, y=yon_av, upper=yon_av+yon_err, lower=yon_av-yon_err)

                x_off_av, yoff_av, yoff_err = avg_off[n]
                selected_block["abs"]["sources"]["off_av"][n].data=dict(x=x_off_av, y=yoff_av, upper=yoff_av+yoff_err, lower=yoff_av-yoff_err)

                # Calculate ratio error from on/off averages using error propagation
                yratio_av = yon_av / yoff_av if np.all(yoff_av != 0) else np.nan * np.ones_like(yon_av)
                yratio_err = np.sqrt((yon_err/yoff_av)**2 + (yon_av/(yoff_av**2)*yoff_err)**2) if np.all(yoff_av != 0) else np.nan * np.ones_like(yon_av)

                selected_block["ratio"]["sources"]["ratio_av"][n].data=dict(x=x_on_av, y=yratio_av, upper=yratio_av+yratio_err, lower=yratio_av-yratio_err)
        # MANUALLY REBUILD LEGENDS FOR 'SELECTED' ONLY
        for panel_key in ["abs", "ratio"]:
            fig = selected_block[panel_key]["fig"]
            new_items = []
            
            # Check if we have active channels to represent the legend
            if self.active_channels:
                # Use the first active channel as the visual 'proxy' for the legend line style
                proxy_ch = self.active_channels[0]
                
                # Determine which source key to use based on the panel
                mode = "on" if panel_key == "abs" else "ratio"
                renderer = selected_block[panel_key]["lines"][mode][proxy_ch]
                
                # Create one legend entry per run
                for i, run_id in enumerate(sd.keys()):
                    label = f"Run {run_id}"
                    # 'index' tells Bokeh which specific line inside the MultiLine to look at
                    new_items.append(LegendItem(label=label, renderers=[renderer], index=i))
            
            fig.legend.items = new_items

        self.table_source.selected.indices = []

    def on_created_cb(self):
        cols, data = self.get_run_table_data()
        data["selected"] = self.table_source.data["selected"]
        self.table_source.data = data

    def on_modified_cb(self):
        data = self.read_file(config.file_name)
        if len(data.shape)>1:
            current_block = self.figures["current"]
            nadj = data.shape[0]-48
            for n in range(8):
                x, yon, yoff, yon_std, yoff_std, yon_nshots, yoff_nshots =data[[0,nadj+n,nadj+n+8,nadj+n+16,nadj+n+24,nadj+n+32,nadj+n+40],:]
                yon_err = yon_std/np.sqrt(yon_nshots)
                yoff_err = yoff_std/np.sqrt(yoff_nshots)
                yratio_err = np.sqrt((yon_err/yoff)**2+(yon/yoff**2*yoff_err)**2)
                current_block["abs"]["sources"]["on"][n].data=dict(x=x, y=yon, upper=yon+yon_err, lower=yon-yon_err)
                current_block["abs"]["sources"]["off"][n].data=dict(x=x, y=yoff, upper=yoff+yoff_err, lower=yoff-yoff_err)
                current_block["ratio"]["sources"]["ratio"][n].data=dict(x=x, y=yon/yoff, upper=yon/yoff + yratio_err, lower = yon/yoff - yratio_err)
    
dv = Data_Visualization()





