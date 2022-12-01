from tkinter import Wm
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
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
import pyaudio

plt.style.use('bmh')
p = pyaudio.PyAudio()

SAMPLESIZE = 220 # number of data points to read at a time default 4096
SAMPLERATE = 220000 # time resolution of the recording self.device (Hz) 44100
TIMESAMPLE = 1 #in second
DISTANCE = 100

# stream=p.open(format=pyaudio.paFloat32,channels=1,rate=SAMPLERATE,input=True,frames_per_buffer=SAMPLESIZE)

data_signal = np.zeros(50)
# print(data_signal)
data_colormap = np.zeros((SAMPLESIZE, DISTANCE))
# print(data_heatmap)
data_adc = np.zeros(20)

Window.clearcolor = (.9, .9, .9, 1)
Window.fullscreen = 'auto'
# Window.fullscreen = True
# Window.size = (2880 , 1920)
kivy.require('2.1.0')

# Designate Our .kv design file 
kv = Builder.load_file('main.kv')
# Builder.load_file('main.kv')
#Define our different screens
class MainWindow(BoxLayout):
    checks = []
    flag_signal = False
    flag_graph = False
    flag_map = False

    dt_waveform = ""
    lon = 107.6213
    lat = -6.8775
    zoom = 19
    # dt_colormap = np.random.randn(5000, 3000)
    dt_distance = 0
    last_distance = 0
    dt_delay = 0
    dt_interval = 10

    def __init__(self):
        super(MainWindow, self).__init__()

        self.fig1, self.ax = plt.subplots()
        # self.fig2, (self.ax1, self.ax2, self.ax3) = plt.subplots(nrows=1, ncols=3, gridspec_kw={'width_ratios': [10, 1, 1]})
        self.fig2, (self.ax1, self.ax2) = plt.subplots(nrows=1, ncols=2, gridspec_kw={'width_ratios': [10, 2]})
        self.setting_screen()

    def hide_widget(self, wid, dohide=True):
        if hasattr(wid, 'saved_attrs'):
            if not dohide:
                wid.height, wid.size_hint_x,  wid.size_hint_y, wid.opacity, wid.disabled = wid.saved_attrs
                del wid.saved_attrs
        elif dohide:
            wid.saved_attrs = wid.height, wid.size_hint_x, wid.size_hint_y, wid.opacity, wid.disabled
            wid.height, wid.size_hint_x, wid.size_hint_y, wid.opacity, wid.disabled = 0, None, None, 0, True

    def setting_screen(self):
        # self.ids.layout_graph_carrier.add_widget(FigureCanvasKivyAgg(self.fig1))
        self.ids.layout_graph_signal.clear_widgets()

        self.hide_widget(self.ids.layout_setting, False)
        self.hide_widget(self.ids.layout_graph, True)
        self.hide_widget(self.ids.layout_map, True)

        self.ids.bt_screen_setting.disabled = True
        self.ids.bt_screen_graph.disabled = False
        self.ids.bt_screen_map.disabled = False

        self.ids.bt_update_graph.disabled = True
        self.ids.bt_update_map.disabled = True

        self.ids.label_page.text = "SETTING SCREEN"

    def graph_screen(self):
        self.ids.layout_graph_carrier.clear_widgets()

        self.hide_widget(self.ids.layout_setting, True)
        self.hide_widget(self.ids.layout_graph, False)
        self.hide_widget(self.ids.layout_map, True)

        self.ids.bt_screen_setting.disabled = False
        self.ids.bt_screen_graph.disabled = True
        self.ids.bt_screen_map.disabled = False

        self.ids.bt_update_graph.disabled = False
        self.ids.bt_update_map.disabled = True

        self.ids.label_page.text = "GRAFIK SCREEN"

    def map_screen(self):
        self.ids.layout_graph_carrier.clear_widgets()
        self.ids.layout_graph_signal.clear_widgets()

        self.hide_widget(self.ids.layout_setting, True)
        self.hide_widget(self.ids.layout_graph, True)
        self.hide_widget(self.ids.layout_map, False)

        self.ids.bt_screen_setting.disabled = False
        self.ids.bt_screen_graph.disabled = False
        self.ids.bt_screen_map.disabled = True

        self.ids.bt_update_graph.disabled = True
        self.ids.bt_update_map.disabled = False

        self.ids.label_page.text = "PETA SCREEN"

    def refresh(self):
        ports = serial.tools.list_ports.comports()
        for port, desc, hwid in sorted(ports):
            print("{}: {} [{}]".format(port, desc, hwid))                
            self.com = str(port)
        try:
            self.ids.txt_com.text = self.com
            self.device = serial.Serial(port=self.com, baudrate=115200, timeout=.1)
            self.ids.bt_open_close_serial.disabled = False
            self.ids.txt_com.disabled = True
            self.ids.bt_refresh.disabled = True
            self.ids.bt_send_signal.disabled = False
            self.ids.bt_open_close_serial.text = "CLOSE COMMUNICATION"
            Clock.schedule_interval(self.update_data, 0.1)
            Clock.schedule_interval(self.update_enco, 1)
            print("success open communication")
            self.ids.label_notif.text = "success open communication"
            self.ids.label_notif.color = 0,0,1
        except:
            print("error open communication")
            self.ids.label_notif.text = "error open communication"
            self.ids.label_notif.color = 1,0,0

    def update_data(self, interval):
        # print("read")
        try:
            if self.device.in_waiting > 0:
                serialString = self.device.readline()
                # print(serialString)
                decodedSerialString = serialString.decode("utf-8")
                print(decodedSerialString)
            
                data_json = json.loads(decodedSerialString)
                print(data_json)

                if(data_json["type"] == "ENCO"):
                    print("get encoder")

                    self.dt_slider_distance = data_json["Pos"]
                    self.ids.slider_distance.value = int(self.dt_slider_distance)
                    self.dt_distance = int(self.ids.slider_distance.value / 1000)
                    
                    print("success update encoder data")
                    self.ids.label_notif.text = "success update encoder data"
                    self.ids.label_notif.color = 0,0,1

                    self.last_distance = self.dt_distance


                elif(data_json["type"] == "GPS"):
                    print("get gps")

                    sign_ns = 1
                    sign_ew = 1
                    ns = data_json["ns"]
                    ew = data_json["ew"]

                    if(ns > 50):
                        sign_ns = -1
                    
                    if(ew > 100):
                        sign_ew = -1

                    self.lon = (data_json["long"] * sign_ew / 100) + 0.248
                    print(self.lon)
                    self.ids.txt_lon.text = str(format(self.lon, '.3f'))

                    self.lat = (data_json["lat"] * sign_ns / 100) - 0.35
                    print(self.lat)
                    self.ids.txt_lat.text = str(format(self.lat, '.3f'))

                    self.map_mark()

                    print("success update map data")
                    self.ids.label_notif.text = "success update map data"
                    self.ids.label_notif.color = 0,0,1
        except:
            print("error reading data")
            self.ids.label_notif.text = "error reading data"
            self.ids.label_notif.color = 1,0,0

    def update_graph(self):
        stream = p.open(format=pyaudio.paFloat32,
                        channels = 1,
                        rate = SAMPLERATE,
                        frames_per_buffer = SAMPLESIZE,
                        input = True)
        
        x = np.linspace(0, SAMPLESIZE-1, SAMPLESIZE)

        # for i in range(0, int(SAMPLERATE / SAMPLESIZE * TIMESAMPLE)):self.dt_interval
        # for i in range(0, int(SAMPLERATE / SAMPLESIZE * self.dt_interval / 5)):
        for i in range(0, int(SAMPLERATE / SAMPLESIZE * TIMESAMPLE)):
            data_signal = np.frombuffer(stream.read(SAMPLESIZE), dtype=np.float32)
          
        x_spec = np.fft.fftfreq(SAMPLESIZE, d = 1.0 / SAMPLERATE)
        y_temp = np.fft.fft(-data_signal[0:SAMPLESIZE])
        y_spec = np.asarray([np.sqrt(c.real ** 2 + c.imag ** 2) for c in y_temp])

        self.dt_distance = int(self.ids.slider_distance.value / 1000)

        data_colormap[: , self.dt_distance] = data_signal

        stream.stop_stream()
        stream.close()

        self.fig2, (self.ax1, self.ax2) = plt.subplots(nrows=1, ncols=2, gridspec_kw={'width_ratios': [10, 2]})
        self.fig2.tight_layout(pad=1.0)
        self.fig2.set_facecolor((.9,.9,.9))
       
        self.ax1.axis([0,DISTANCE, SAMPLESIZE,0])
        self.ax1.set_xlabel('distance (m)', fontsize=20)
        self.ax1.set_ylabel('depth (m)', fontsize=20)
        self.ax1.grid(False)

        clrmesh = self.ax1.pcolor(data_colormap, cmap='seismic', vmin=-0.1, vmax=0.1)
        self.fig2.colorbar(clrmesh, ax=self.ax1, format='%f')

        self.ax2.axis([-0.1, 0.1, SAMPLESIZE-1, 0])
        self.ax2.set_xlabel('amplitude (dB)', fontsize=20)
        self.ax2.set_ylabel('time (sample)', fontsize=20)
        self.ax2.plot(data_signal, x, lw=1)

        # self.ax3.axis([0,25, SAMPLERATE/32, 0])
        # self.ax3.set_xlabel('amplitude (dB)', fontsize=20)
        # self.ax3.set_ylabel('frequency (Hz)', fontsize=20)
        # self.ax3.plot(y_spec, -x_spec, lw=1,marker= 'o', linestyle='-')

        self.ids.layout_graph_signal.clear_widgets()
        self.ids.layout_graph_signal.add_widget(FigureCanvasKivyAgg(self.fig2))

    def update_enco(self, interval):
        data_json = json.dumps({"type":"ENCO"})
        str_send = data_json + "\n"
        self.device.write(str_send.encode())        
        print(str_send)

    def update_map(self, interval):
        data_json = json.dumps({"type":"GPS"})
        str_send = data_json + "\n"
        self.device.write(str_send.encode())        
        print(str_send)

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

    def open_close_serial(self):
        if (self.device.isOpen()):
            self.device.close()
            self.ids.txt_com.disabled = False
            self.ids.bt_refresh.disabled = False
            self.ids.bt_send_signal.disabled = True            
            self.ids.bt_open_close_serial.text = "OPEN COMMUNICATION"
            Clock.unschedule(self.update_data)
            Clock.unschedule(self.update_enco)
            print("communication port is closed")
            self.ids.label_notif.text = "communication port is closed"
            self.ids.label_notif.color = 0,0,1
        else:
            self.device.open()
            self.ids.txt_com.disabled = True
            self.ids.bt_refresh.disabled = True
            self.ids.bt_send_signal.disabled = False
            self.ids.bt_open_close_serial.text = "CLOSE COMMUNICATION"
            Clock.schedule_interval(self.update_data, 0.1)
            Clock.schedule_interval(self.update_enco, 1)
            print("communication port is opened")
            self.ids.label_notif.text = "communication port is opened"
            self.ids.label_notif.color = 0,0,1
            
    def stop_signal(self):
        self.flag_signal = False
        self.ids.bt_send_signal.text = "GENERATE SIGNAL"

        data_json = json.dumps({"type":"STOP"})
        str_send = data_json + "\n"
        self.device.write(str_send.encode())
        print(str_send)            

        print("signal stopped")
        self.ids.label_notif.text = "signal stopped"
        self.ids.label_notif.color = 1,0,0

    def send_signal(self):
        self.dt_frequency_min = self.ids.slider_min.value
        self.dt_frequency_max = self.ids.slider_max.value
        self.dt_interval = self.ids.slider_interval.value

        offset = (self.dt_frequency_max + self.dt_frequency_min) / 2
        amplitude = (self.dt_frequency_max - self.dt_frequency_min) / 2

        x_axis = np.linspace(0, 100, int(10000/self.dt_interval), endpoint=True) #20 data per periode in 100ms axis

        if("SEGITIGA" in self.dt_waveform):
            y_axis = offset + (4 * amplitude / self.dt_interval) * np.abs((((x_axis - self.dt_interval / 4) % self.dt_interval) + self.dt_interval) % self.dt_interval - self.dt_interval / 2 ) - amplitude
            data_adc = np.round(0.0 + (1.0 - 0.0) * ((y_axis - 160) / (360 - 160)) , 2)
            # print(y_axis)
        elif("PERSEGI" in self.dt_waveform):
            y_axis = offset + (amplitude * np.sign (np.sin(2 * np.pi * 1 / self.dt_interval * x_axis)))
            data_adc = np.round(0.0 + (1.0 - 0.0) * ((y_axis - 160) / (360 - 160)) , 2)
            # print(y_axis)
        elif("GIGI GERGAJI" in self.dt_waveform):
            y_axis = self.dt_frequency_min + ((2 * amplitude / self.dt_interval) * (x_axis % self.dt_interval))
            data_adc = np.round(0.0 + (1.0 - 0.0) * ((y_axis - 160) / (360 - 160)) , 2)
            # print(y_axis)
        else:
            y_axis = 0 * x_axis
            data_adc = y_axis

        if(self.flag_signal):
            y_axis = 0 * x_axis
            self.stop_signal()

        else:
            self.flag_signal = True
            self.ids.bt_send_signal.text = "STOP SIGNAL"
            try:
                data_json = json.dumps({"type":"DAC","value":list(data_adc[0:99:5]),"periode":self.dt_interval})
                str_send = data_json + "\n"
                self.device.write(str_send.encode())
                print(str_send)

                print("success generating signal")
                self.ids.label_notif.text = "success generating signal"
                self.ids.label_notif.color = 0,0,1
            except:
                print("error generating signal")
                self.ids.label_notif.text = "error generating signal"
                self.ids.label_notif.color = 1,0,0

        self.fig1, self.ax = plt.subplots()
        self.fig1.set_facecolor((.9,.9,.9))
        self.ax.set_facecolor((.9,.9,.9))
        self.ax.plot(x_axis, y_axis)

        self.ids.layout_graph_carrier.clear_widgets()
        self.ids.layout_graph_carrier.add_widget(FigureCanvasKivyAgg(self.fig1))

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

        # if(self.flag_graph):
        #     Clock.unschedule(self.update_enco)
        #     self.ids.bt_screen_setting.disabled = False
        #     self.ids.bt_screen_map.disabled = False

        #     self.ids.bt_update_graph.text = "UPDATE GRAPH"
        #     self.flag_graph = False

        # else:
        #     Clock.schedule_interval(self.update_enco, 0.1)
        #     self.ids.bt_screen_setting.disabled = True
        #     self.ids.bt_screen_map.disabled = True

        #     self.ids.bt_update_graph.text = "UPDATING GRAPH..."
        #     self.flag_graph = True


    def checkbox_click(self, instance, value, waves):
        if value == True:
            self.checks.append(waves)
            waveforms = ''
            for x in self.checks:
                waveforms = f'{waveforms} {x}'
            self.ids.output_label.text = f'BENTUK GELOMBANG {waveforms} DIPILIH'
        else:
            self.checks.remove(waves)
            waveforms = ''
            for x in self.checks:
                waveforms = f'{waveforms} {x}'
            self.ids.output_label.text = f'BENTUK GELOMBANG {waveforms} DIPILIH'
        
        self.dt_waveform = waveforms


class GPRApp(App):
    def build(self):
        self.icon = 'asset/logo.ico'
      
        return MainWindow()

if __name__ == '__main__':
	GPRApp().run()
