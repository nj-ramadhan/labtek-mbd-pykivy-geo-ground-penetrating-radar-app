import serial, serial.tools.list_ports
import numpy as np
import json
import kivy
import sys
import os
from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.config import Config
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.figure import Figure
import matplotlib.colors as mcolors
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
import pyaudio
from datetime import datetime
# from segpy.writer import write_segy

plt.style.use('bmh')
p = pyaudio.PyAudio()

BANDWITH = 20000
MEDIUMSPEED = 300000000
TAO = 1

SAMPLESIZE = 500 # number of data points to read at a time default 4096
SAMPLERATE = 100000 # time resolution of the recording self.device (Hz) 44100
TIMESAMPLE = 0.01 #in second
DISTANCE = 10

DEFTOPGAIN = 1.0
DEFBOTTOMGAIN = 2.0
# DEFMINGRAPH = 0
# DEFMAXGRAPH = 1

Window.clearcolor = (.9, .9, .9, 1)
Window.fullscreen = 'auto'
kivy.require('2.1.0')

# Designate Our .kv design file 
kv = Builder.load_file('main.kv')

class MainWindow(BoxLayout):
    checks_waveform = []
    checks_method = []
    flag_signal = False
    flag_graph = False
    flag_map = False
    flag_move = False

    dt_waveform = ""
    dt_method = ""
    lon = 107.6213
    lat = -6.8775
    zoom = 19
    dt_slider_distance = 0
    dt_distance = 0
    last_distance = 0
    dt_delay = 0
    dt_interval = 10
    # min_graph = 0
    # max_graph = 50
    top_gain = 5
    bottom_gain = 20

    data_signal = np.zeros(50)
    data_colormap = np.zeros((SAMPLESIZE, DISTANCE))
    data_wiggles = np.zeros((SAMPLESIZE, 1))
    data_samples = np.zeros((SAMPLESIZE, 1))
    data_adc = np.zeros(20)

    def __init__(self):
        super(MainWindow, self).__init__()

        self.fig1, self.ax = plt.subplots()
        # self.fig2, (self.ax1, self.ax2, self.ax3) = plt.subplots(nrows=1, ncols=3, gridspec_kw={'width_ratios': [10, 1, 1]})
        self.fig2, (self.ax1, self.ax2) = plt.subplots(nrows=1, ncols=2, gridspec_kw={'width_ratios': [10, 2]})
        # self.ids.slider_min_graph.value = DEFMINGRAPH
        # self.ids.slider_max_graph.value = DEFMAXGRAPH
        self.ids.slider_top_gain.value = DEFTOPGAIN
        self.ids.slider_bottom_gain.value = DEFBOTTOMGAIN
        self.ids.slider_distance.max = DISTANCE

        self.graph_screen()

    def hide_widget(self, wid, dohide=True):
        if hasattr(wid, 'saved_attrs'):
            if not dohide:
                wid.height, wid.size_hint_x,  wid.size_hint_y, wid.opacity, wid.disabled = wid.saved_attrs
                del wid.saved_attrs
        elif dohide:
            wid.saved_attrs = wid.height, wid.size_hint_x, wid.size_hint_y, wid.opacity, wid.disabled
            wid.height, wid.size_hint_x, wid.size_hint_y, wid.opacity, wid.disabled = 0, None, None, 0, True

    def graph_screen(self):
        # self.ids.layout_graph_carrier.clear_widgets()

        self.hide_widget(self.ids.layout_graph_setting, False)
        self.hide_widget(self.ids.layout_graph, False)
        self.hide_widget(self.ids.layout_map, True)

        # self.ids.bt_screen_setting.disabled = False
        self.ids.bt_screen_graph.disabled = True
        self.ids.bt_screen_map.disabled = False

        self.ids.bt_save_data.disabled = False
        self.ids.bt_save_graph.disabled = False
        self.ids.bt_update_map.disabled = True

        self.ids.label_page.text = "GRAPH SCREEN"

        if("CONTINUOUS" in self.dt_method):
            self.ids.bt_update_graph.disabled = True
            Clock.schedule_interval(self.update_graph_time, 2)

        elif("MANUAL" in self.dt_method):
            self.ids.bt_update_graph.disabled = False
            Clock.unschedule(self.update_graph_time)

        else:
            self.ids.bt_update_graph.disabled = False
            Clock.unschedule(self.update_graph_time)


    def map_screen(self):
        # self.ids.layout_graph_carrier.clear_widgets()
        self.ids.layout_graph_signal.clear_widgets()

        self.hide_widget(self.ids.layout_graph_setting, True)
        self.hide_widget(self.ids.layout_graph, True)
        self.hide_widget(self.ids.layout_map, False)

        # self.ids.bt_screen_setting.disabled = False
        self.ids.bt_screen_graph.disabled = False
        self.ids.bt_screen_map.disabled = True

        self.ids.bt_update_graph.disabled = True
        self.ids.bt_save_data.disabled = True
        self.ids.bt_save_graph.disabled = True
        self.ids.bt_update_map.disabled = False

        self.ids.label_page.text = "MAP SCREEN"
        Clock.unschedule(self.update_graph_time)

    def update_graph_time(self, interval):
        self.update_graph()
        self.dt_slider_distance += 1000
        self.ids.slider_distance.value = float(self.dt_slider_distance / 1000)
        self.dt_distance = int(self.dt_slider_distance / 1000)

    def update_graph(self):
        # self.min_graph = self.ids.slider_min_graph.value
        # self.max_graph = self.ids.slider_max_graph.value
        self.top_gain = self.ids.slider_top_gain.value
        self.bottom_gain = self.ids.slider_bottom_gain.value
        
        stream = p.open(format=pyaudio.paFloat32,
                        channels = 1,
                        rate = SAMPLERATE,
                        frames_per_buffer = SAMPLESIZE,
                        input = True)
        
        x = np.linspace(0, SAMPLESIZE-1, SAMPLESIZE)

        for i in range(0, int(SAMPLERATE / SAMPLESIZE * TIMESAMPLE)):
            self.data_signal = np.frombuffer(stream.read(SAMPLESIZE), dtype=np.float32)

        x_spec = np.fft.fftfreq(SAMPLESIZE, d = 1.0 / SAMPLERATE)
        y_temp = np.fft.fft(self.data_signal[0:SAMPLESIZE])
        y_spec = np.asarray([np.sqrt(c.real ** 2 + c.imag ** 2) for c in y_temp])
        y_gain = np.array([SAMPLESIZE])
        y_intime = np.fft.ifft(y_spec).real
        y_wiggle = np.asarray([np.sqrt(c.real ** 2 + c.imag ** 2) for c in y_intime])

        self.dt_distance = int(self.dt_slider_distance / 1000)

        x_gain = np.linspace(0, SAMPLESIZE-1, SAMPLESIZE)
        y_gain = ( x_gain * (self.bottom_gain - self.top_gain) / SAMPLESIZE) + self.top_gain

            # for i in range (0, SAMPLESIZE):
            #     y_spec[i] = y_spec[i] * y_gain[i]
        
        for i in range (0, SAMPLESIZE):
            y_wiggle[i] = y_wiggle[i] * y_gain[i]

        if(self.dt_distance >= DISTANCE):
            # temp_data_signal = y_spec
            temp_data_signal = y_wiggle
            temp_data_signal.resize([SAMPLESIZE, 1])
            self.data_colormap = np.concatenate([self.data_colormap, temp_data_signal], axis=1)
            self.data_wiggles = np.concatenate([self.data_wiggles, temp_data_signal], axis=1)
            temp_data_samples = -x_spec
            temp_data_samples.resize([SAMPLESIZE, 1])   
            self.data_samples = np.concatenate([self.data_samples, temp_data_samples], axis=1)
            self.ids.slider_distance.max += 1
            
        else:
            # self.data_colormap[: , self.dt_distance] = y_spec
            self.data_colormap[: , self.dt_distance] = y_wiggle
            temp_data_signal = y_wiggle
            temp_data_signal.resize([SAMPLESIZE, 1])            
            self.data_wiggles = np.concatenate([self.data_wiggles, temp_data_signal], axis=1)
            temp_data_samples = -x_spec
            temp_data_samples.resize([SAMPLESIZE, 1])    
            self.data_samples = np.concatenate([self.data_samples, temp_data_samples], axis=1)

        stream.stop_stream()
        stream.close()

        # self.fig2, (self.ax1, self.ax2, self.ax3) = plt.subplots(nrows=1, ncols=3, gridspec_kw={'width_ratios': [10, 2, 1]})
        self.fig2, (self.ax1, self.ax2) = plt.subplots(nrows=1, ncols=2, gridspec_kw={'width_ratios': [10, 2]})
        self.fig2.tight_layout()
        self.fig2.set_facecolor((.9,.9,.9))
        
        # #plot color
        # self.ax1.axis([0,DISTANCE, (SAMPLESIZE/2),0])
        # #self.ax1.set_ylabel('frequency (Hz)', fontsize=20)
        # # self.ax1.set_ylabel('time (ms)', fontsize=20)
        # self.ax1.yaxis.set_ticks_position('right')
        # self.ax1.set_xlabel('distance (m)', fontsize=20)
        # # self.ax1.set_ylabel('depth (m)', fontsize=20)
        # secax = self.ax1.secondary_yaxis('left', functions=(self.freq_to_depth, self.depth_to_freq))
        # secax.set_ylabel('depth (m)', fontsize=20)
        # #self.ax1.yaxis.set_ticks(np.arange(self.freq_to_depth(0), self.freq_to_depth(250), 100000))

        # self.ax1.set_xlim(0, self.ids.slider_distance.max)
        # self.ax1.grid(False)
     
        # clrmesh = self.ax1.pcolor(self.data_colormap, cmap='turbo', vmin=self.min_graph, vmax=self.max_graph)
        # self.fig2.colorbar(clrmesh, ax=self.ax1, format='%3.2f')

        #plot wiggle
        # Some example data
        # self.ax1.axis([0,DISTANCE, (SAMPLESIZE/2),0])
        self.ax1.set_xlabel('distance (m)', fontsize=20)
        self.ax1.set_ylabel('depth', fontsize=20)
        offsets = np.linspace(0, self.dt_distance-1, self.dt_distance)
       
        for offset, wiggle, sample in zip(offsets, self.data_wiggles.T, self.data_samples.T):
            x = offset + wiggle
            y = sample

            self.ax1.plot(x, y, lw=1, linestyle='-', color='k')
            self.ax1.fill_betweenx(y, offset, x, where=(x > offset), color='k')

        self.ax1.set_xlim(0, self.ids.slider_distance.max)
        self.ax1.set_ylim(SAMPLESIZE/TIMESAMPLE, 0)

        # self.ax2.axis([self.min_graph, self.max_graph, SAMPLESIZE/TIMESAMPLE, 0])
        self.ax2.set_ylim(SAMPLESIZE/TIMESAMPLE, 0)
        self.ax2.set_xlabel('amplitude', fontsize=20)
        # self.ax2.set_ylabel('frequency (Hz)', fontsize=20)
        # self.ax2.plot(y_spec, -x_spec, lw=1,marker= 'o', linestyle='-')
        # self.ax2.plot(y_wiggle, -x_spec, lw=1,marker= 'o', linestyle='-')
        self.ax2.plot(y_wiggle, -x_spec, lw=1, linestyle='-', color='k')

        # self.ax3.axis([0, np.max(y_gain), -SAMPLESIZE, 0])
        # self.ax3.set_xlabel('gain', fontsize=20)
        # self.ax3.plot(y_gain, -x_gain, lw=1, linestyle='-', color='k')
        
        self.ids.layout_graph_signal.clear_widgets()
        self.ids.layout_graph_signal.add_widget(FigureCanvasKivyAgg(self.fig2))

    def freq_to_depth(self, freq):
        return (freq * (MEDIUMSPEED * TAO) / (2 * BANDWITH))

    def depth_to_freq(self, depth):
        return (depth * (2 * BANDWITH) / (MEDIUMSPEED * TAO))
    
    def update_enco(self, interval):
        try:
            data_json = json.dumps({"type":"ENCO"})
            str_send = data_json + "\n"
            self.device.write(str_send.encode())        
            print(str_send)
        except:
            print("error updating encoder")
            self.ids.label_notif.text = "error updating encoder"
            self.ids.label_notif.color = 1,0,0

    def update_map(self, interval):
        try:
            data_json = json.dumps({"type":"GPS"})
            str_send = data_json + "\n"
            self.device.write(str_send.encode())        
            print(str_send)
        except:
            print("error updating map")
            self.ids.label_notif.text = "error updating map"
            self.ids.label_notif.color = 1,0,0
            

    def map_mark(self):
        self.lon = float(self.ids.txt_lon.text)
        self.lat = float(self.ids.txt_lat.text)
        self.zoom = int(self.ids.slider_zoom.value)

        self.ids.map_view.lon = self.lon
        self.ids.map_view.lat = self.lat
        self.ids.map_view.zoom = self.zoom

        self.ids.map_marker.lon = self.lon
        self.ids.map_marker.lat = self.lat

        print("long:" + str(self.lon) + ", lat:" + str(self.lat) + ", zoom:" + str(self.zoom))

    def request_map(self):
        if(self.flag_map):
            Clock.unschedule(self.update_map)
            self.ids.bt_screen_setting.disabled = False
            self.ids.bt_screen_graph.disabled = False

            self.ids.bt_update_map.text = "UPDATE MAP"
            self.flag_map = False

        else:
            Clock.schedule_interval(self.update_map, 2)
            self.ids.bt_screen_setting.disabled = True
            self.ids.bt_screen_graph.disabled = True

            self.ids.bt_update_map.text = "UPDATING MAP..."
            self.flag_map = True
            
    def request_graph(self):
        self.update_graph()
        self.dt_slider_distance += 1000
        self.ids.slider_distance.value = float(self.dt_slider_distance / 1000)
        self.dt_distance = int(self.dt_slider_distance / 1000)

    def save_data(self):
        try:
            now = datetime.now().strftime("%d_%m_%Y_%H_%M_%S.segy")
            with open(now,"wb") as f:
                np.savetxt(f, self.data_colormap, fmt="%f")
                # write_segy(f, self.data_colormap, endian=">")
            print("sucessfully save data")
            self.ids.label_notif.text = "sucessfully save data"
            self.ids.label_notif.color = 0,0,1
        except:
            print("error saving data")
            self.ids.label_notif.text = "error saving data"
            self.ids.label_notif.color = 1,0,0

    def save_graph(self):
        try:
            now = datetime.now().strftime("%d_%m_%Y_%H_%M_%S.jpg")
            self.fig2.savefig(now)
            print("sucessfully save graph")
            self.ids.label_notif.text = "sucessfully save graph"
            self.ids.label_notif.color = 0,0,1
        except:
            print("error saving graph")
            self.ids.label_notif.text = "error saving graph"
            self.ids.label_notif.color = 1,0,0

    def reset_graph(self):
        # self.ids.slider_min_graph.value = DEFMINGRAPH
        # self.ids.slider_max_graph.value = DEFMAXGRAPH
        self.min_graph = self.ids.slider_min_graph.value
        self.max_graph = self.ids.slider_max_graph.value

    def reset_gain(self):
        self.ids.slider_top_gain.value = DEFTOPGAIN
        self.ids.slider_bottom_gain.value = DEFBOTTOMGAIN
        self.top_gain = self.ids.slider_top_gain.value
        self.bottom_gain = self.ids.slider_bottom_gain.value

    def exec_exit(self):
        quit()

    def exec_shutdown(self):
        os.system("shutdown /s /t 1")

    def checkbox_method_click(self, instance, value, meths):
        if value == True:
            self.checks_method.append(meths)
            methods = ''
            for x in self.checks_method:
                methods = f'{methods} {x}'
        else:
            self.checks_method.remove(meths)
            methods = ''
            for x in self.checks_method:
                methods = f'{methods} {x}'
        
        self.dt_method = methods

        if("CONTINUOUS" in self.dt_method):
            self.ids.bt_update_graph.disabled = True
            Clock.schedule_interval(self.update_graph_time, 2)

        elif("MANUAL" in self.dt_method):
            self.ids.bt_update_graph.disabled = False
            Clock.unschedule(self.update_graph_time)

        else:
            self.ids.bt_update_graph.disabled = False
            Clock.unschedule(self.update_graph_time)


class GPRApp(App):
    def build(self):
        self.icon = 'asset/logo.ico'
      
        return MainWindow()

if __name__ == '__main__':
	GPRApp().run()
